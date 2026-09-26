import json
import hashlib
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODEL = os.environ.get("DELPHI_CODE_TEST_MODEL")


@unittest.skipUnless(MODEL, "Set DELPHI_CODE_TEST_MODEL to a provisioned local model")
class OfflineCLI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory(prefix="delphi-code-test-")
        cls.base = Path(cls.workspace.name).resolve()
        cls.project = cls.base / "project"
        cls.project.mkdir()
        cls.index_root = cls.base / "indexes"
        cls.state = cls.index_root / hashlib.sha256(os.fsencode(cls.project.resolve())).hexdigest()
        cls.audit = cls.base / "audit"
        cls.audit.mkdir()
        (cls.audit / "sitecustomize.py").write_text(
            "import os, sys\n"
            "def audit(event, args):\n"
            "    if event in {'socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.sendto'}:\n"
            "        if event != 'socket.connect' or getattr(args[0], 'family', None) in (2, 10, 30):\n"
            "            with open(os.environ['DELPHI_CODE_NETWORK_LOG'], 'a') as stream:\n"
            "                stream.write(event + '\\n')\n"
            "            raise RuntimeError('Network attempted during offline test')\n"
            "sys.addaudithook(audit)\n"
        )
        cls.network_log = cls.base / "network.log"
        cls.env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(cls.audit), str(ROOT)]),
                       DELPHI_CODE_INDEX_ROOT=str(cls.index_root), HF_HOME=str(cls.base / "empty-hf-cache"), DELPHI_CODE_NETWORK_LOG=str(cls.network_log),
                       COCOINDEX_DISABLE_USAGE_TRACKING="0", HF_HUB_OFFLINE="0", HF_HUB_DISABLE_TELEMETRY="0")

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def invoke(self, *args, code=0, model=MODEL, project=True):
        command = [sys.executable, "-m", "delphi_code", *args]
        if project:
            command.extend(["--project", str(self.project)])
        if args[0] != "status":
            command.extend(["--model", str(model)])
        result = subprocess.run(command, env=self.env, text=True, capture_output=True, timeout=120)
        self.assertEqual(result.returncode, code, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["ok"], code == 0)
        self.assertFalse(self.network_log.exists(), self.network_log.read_text() if self.network_log.exists() else "")
        return payload.get("data", payload.get("error"))

    def test_setup_import_and_reuse(self):
        destination = self.base / "provisioned-model"
        command = [sys.executable, "-m", "delphi_code", "setup", "--from", MODEL, "--model", str(destination)]
        for reused in (False, True):
            result = subprocess.run(command, env=self.env, text=True, capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["data"]["reused"], reused)
            self.assertEqual(payload["data"]["diagnostics"]["dimensions"], 384)
            self.assertEqual(payload["data"]["diagnostics"]["model"], str(destination))
            self.assertFalse(self.network_log.exists())

    def test_workflow(self):
        missing = self.invoke("index", model=self.base / "missing", code=3)
        self.assertEqual(missing["code"], "model_missing")
        self.assertFalse((self.project / ".delphi-code").exists())
        self.assertEqual(self.invoke("search", "password", code=4)["code"], "index_missing")
        doctor = self.invoke("doctor")
        self.assertEqual(doctor["dimensions"], 384)
        self.assertEqual(doctor["self_distance"], 0)
        (self.project / "auth.py").write_text("def authenticate_user(password, expected_password):\n    return password == expected_password\n")
        (self.project / "math.py").write_text("def add_numbers(left, right):\n    return left + right\n")
        (self.project / ".gitignore").write_text("ignored.py\n*.private\n")
        (self.project / "ignored.py").write_text("TOP_SECRET = 'password'\n")
        (self.project / "binary.py").write_bytes(b"\x00\xff")
        (self.project / "nested").mkdir()
        (self.project / "nested/.gitignore").write_text("!keep.private\nhidden.py\n")
        (self.project / "nested/keep.private").write_text("retained text")
        (self.project / "nested/hide.private").write_text("excluded text")
        (self.project / "nested/hidden.py").write_text("excluded code")
        (self.project / "linked.py").symlink_to(self.project / "auth.py")
        initial = self.invoke("index")
        self.assertGreaterEqual(initial["files"], 3)
        self.assertEqual(initial["index_directory"], str(self.state))
        self.assertFalse((self.project / ".delphi-code").exists())
        results = self.invoke("search", "verify user password", "--language", "python", "--limit", "1")["results"]
        self.assertEqual(results[0]["path"], "auth.py")
        across = self.invoke("search", "verify user password", "--limit", "1", project=False)
        self.assertEqual(across["projects"], [str(self.project)])
        self.assertEqual(across["results"][0]["project"], str(self.project))
        self.assertEqual(across["results"][0]["path"], "auth.py")
        self.assertEqual(results[0]["start_line"], 1)
        self.assertEqual(results[0]["end_line"], 2)
        repeated = self.invoke("index")
        self.assertEqual(repeated["incremental"].get("num_adds", 0), 0)
        self.assertEqual(repeated["incremental"].get("num_reprocesses", 0), 0)
        self.assertGreater(repeated["incremental"].get("num_unchanged", 0), 0)
        auth = self.project / "auth.py"
        timestamp = auth.stat()
        auth.write_text("def verify_token(token, expected):\n    return token == expected\n")
        os.utime(auth, ns=(timestamp.st_atime_ns, timestamp.st_mtime_ns))
        (self.project / "math.py").unlink()
        changed = self.invoke("index")
        self.assertGreater(changed["incremental"].get("num_reprocesses", 0), 0)
        self.assertGreater(changed["incremental"].get("num_deletes", 0), 0)
        self.assertEqual(self.invoke("search", "add numbers", "--path", "math.py")["results"], [])
        updated = self.invoke("search", "token", "--path", "auth.py")["results"]
        self.assertIn("verify_token", updated[0]["text"])
        self.assertEqual(self.invoke("search", "excluded", "--path", "nested/hidden.py")["results"], [])
        self.assertEqual(self.invoke("search", "excluded", "--path", "nested/hide.private")["results"], [])
        self.assertEqual(len(self.invoke("search", "retained", "--path", "nested/keep.private")["results"]), 1)
        self.assertTrue(self.invoke("status")["ready"])
        with (self.state / "lock").open("r") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assertEqual(self.invoke("status", code=5)["code"], "index_busy")
            self.assertEqual(self.invoke("search", "token", code=5)["code"], "index_busy")
        manifest = self.state / "manifest.json"
        incomplete = json.loads(manifest.read_text())
        incomplete["ready"] = False
        manifest.write_text(json.dumps(incomplete))
        self.assertEqual(self.invoke("search", "token", code=4)["code"], "index_incomplete")
        self.invoke("index")
        alternative = self.base / "alternative-model"
        alternative.mkdir()
        (alternative / "modules.json").write_text('[{"type":"sentence_transformers.models.Transformer","path":""}]')
        self.assertEqual(self.invoke("index", model=alternative, code=3)["code"], "model_missing")
        (alternative / "model.safetensors").write_bytes(b"invalid")
        self.assertEqual(self.invoke("search", "token", model=alternative, code=4)["code"], "model_mismatch")
        self.assertEqual(self.invoke("doctor", model=alternative, code=3)["code"], "model_invalid")
        self.invoke("search", "token", "--limit", "0", code=2)
        self.invoke("index", "--language", "python", "--ignore", "auth.py")
        self.assertEqual(self.invoke("search", "token")["results"], [])


class NetworkSandbox(unittest.TestCase):
    @unittest.skipUnless(os.environ.get("DELPHI_CODE_OS_SANDBOX") == "1", "Run via scripts/test_offline.sh")
    def test_os_denies_network(self):
        probe = subprocess.run(
            [sys.executable, "-c",
             "import socket, sys\n"
             "with socket.socket() as sock:\n"
             "    try:\n"
             "        sock.connect(('127.0.0.1', 9))\n"
             "    except PermissionError:\n"
             "        sys.exit(0)\n"
             "    raise RuntimeError('OS network denial is not active')\n"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(probe.returncode, 0, probe.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
