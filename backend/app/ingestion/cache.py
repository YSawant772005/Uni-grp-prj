"""On-disk cache for downloaded source documents.

Downloads are kept outside the repository (default ``backend/.ingestion_cache``,
gitignored) so repeated runs are cheap and so no restricted dataset is ever
committed. Only public-domain / permissively licensed files are ever cached.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("uni.ingestion")

DEFAULT_DIR = Path(__file__).resolve().parents[2] / ".ingestion_cache"
ENV_VAR = "INGESTION_CACHE_DIR"
KEEP_BYTES = 200 * 1024 * 1024  # keep the local cache bounded


def cache_dir() -> Path:
    return Path(os.environ.get(ENV_VAR, DEFAULT_DIR))


def cache_path(ctx, label: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", label)
    directory = cache_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory / safe


def store(ctx, label: str, payload: bytes) -> None:
    path = cache_path(ctx, label)
    if path.exists():
        path.unlink()
    path.write_bytes(payload)
    meta_path = path.with_suffix(".meta.json")
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (OSError, ValueError):
        meta = {}
    meta["retrieved_at"] = datetime.now(timezone.utc).isoformat()
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def read_meta(ctx, label: str) -> dict:
    meta = cache_path(ctx, label).with_suffix(".meta.json")
    if not meta.exists():
        return {}
    try:
        return json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_meta(ctx, label: str, meta: dict) -> None:
    meta_path = cache_path(ctx, label).with_suffix(".meta.json")
    try:
        existing = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    except (OSError, ValueError):
        existing = {}
    existing.update(meta)
    meta_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def total_bytes() -> int:
    directory = cache_dir()
    if not directory.exists():
        return 0
    return sum(p.stat().st_size for p in directory.glob("*") if p.is_file())


def prune(limit: int = KEEP_BYTES) -> None:
    """Evict least-recently-used downloads once the cache exceeds ``limit``."""
    directory = cache_dir()
    files = [p for p in directory.glob("*") if p.is_file() and not p.name.endswith(".meta.json")]
    if sum(p.stat().st_size for p in files) <= limit:
        return
    for path in sorted(files, key=lambda p: p.stat().st_mtime):
        if sum(p.stat().st_size for p in files) <= limit:
            break
        path.unlink(missing_ok=True)
        path.with_suffix(".meta.json").unlink(missing_ok=True)
        files.remove(path)
        logger.info("pruned cached download %s", path.name)
