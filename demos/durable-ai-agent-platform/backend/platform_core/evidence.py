import hashlib
from pathlib import Path


def runtime_fingerprint() -> str:
    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for folder, extension in [("backend", ".py"), ("sql", ".sql")]:
        for path in sorted(root.joinpath(folder).rglob("*" + extension)):
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_text(encoding="utf-8").encode())
    return digest.hexdigest()
