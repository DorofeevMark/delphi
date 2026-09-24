import fnmatch

from pathspec import GitIgnoreSpec

DEFAULT_EXCLUDES = {".git", ".delphi", ".venv", "venv", "node_modules", "__pycache__", ".models"}


def selected(path, language, paths, languages):
    return (not paths or any(fnmatch.fnmatchcase(path, pattern) for pattern in paths)) and (
        not languages or language in languages
    )


def collect(root, paths, languages, ignores, model_root, max_bytes):
    from cocoindex.ops.text import detect_code_language

    found = {}
    skipped = 0
    extra = GitIgnoreSpec.from_lines(ignores)

    def walk(directory, inherited):
        nonlocal skipped
        rules = list(inherited)
        for name in (".gitignore", ".delphiignore"):
            rule_file = directory / name
            if rule_file.is_file() and not rule_file.is_symlink():
                rules.append((directory, GitIgnoreSpec.from_lines(rule_file.read_text().splitlines())))
        for entry in sorted(directory.iterdir()):
            relative = entry.relative_to(root).as_posix()
            if entry.is_symlink():
                skipped += 1
                continue
            is_dir = entry.is_dir()
            if entry.name in DEFAULT_EXCLUDES or entry == model_root:
                skipped += 1
                continue
            ignored = False
            for base, spec in rules:
                match = spec.check_file(entry.relative_to(base).as_posix() + ("/" if is_dir else ""))
                if match.include is not None:
                    ignored = match.include
            if ignored or extra.match_file(relative + ("/" if is_dir else "")):
                skipped += 1
                continue
            if is_dir:
                walk(entry, rules)
            elif entry.is_file():
                language = detect_code_language(filename=entry.name) or "text"
                if not selected(relative, language, paths, languages):
                    continue
                with entry.open("rb") as stream:
                    data = stream.read(max_bytes + 1)
                if len(data) > max_bytes or b"\0" in data:
                    skipped += 1
                    continue
                try:
                    content = data.decode("utf-8")
                except UnicodeDecodeError:
                    skipped += 1
                    continue
                if content.strip():
                    found[relative] = (relative, language, content)
    walk(root, [])
    return found, skipped
