from __future__ import annotations

import json
import pathlib


def has_session(path: str) -> bool:
    return bool(path) and pathlib.Path(path).exists()


def load_cookies(path: str) -> list[dict]:
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def save_cookies(cookies: list[dict], path: str) -> None:
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cookies), encoding="utf-8")
