import os
import sys

for name in (
    "COCOINDEX_DISABLE_USAGE_TRACKING", "HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE",
    "HF_DATASETS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY", "DO_NOT_TRACK",
    "HF_HUB_DISABLE_PROGRESS_BARS",
):
    os.environ[name] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["COCOINDEX_MAX_INFLIGHT_COMPONENTS"] = "1"


def _deny_network(event, args):
    if event in {"socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"}:
        raise RuntimeError("Offline policy blocked a DNS lookup")
    if event in {"socket.connect", "socket.connect_ex", "socket.bind", "socket.sendto"}:
        if getattr(args[0], "family", None) in (2, 10, 30):
            raise RuntimeError("Offline policy blocked an Internet socket operation")


sys.addaudithook(_deny_network)
