"""Parse drafts from disk: markdown/plaintext with YAML front-matter, JSON, JSONL.

Front-matter support is deliberately a flat ``key: value`` subset of YAML
(the only metadata a draft carries is a handful of scalar fields), which keeps
the tool dependency-free. Unknown keys and malformed values fail loudly as
:class:`LoaderError` — a typo'd ``sequnce_id`` should never silently become an
unlinted draft.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from outreach_lint.models import Draft

_FRONT_MATTER_KEYS = {"id", "touch", "sequence_id", "hook"}
_TEXT_SUFFIXES = {".md", ".txt", ".markdown"}
_JSON_SUFFIXES = {".json", ".jsonl"}


class LoaderError(Exception):
    """Raised when a draft file cannot be parsed into drafts."""


def load_path(path: Path) -> list[Draft]:
    """Load one file, or every supported file in a directory (sorted, non-recursive
    unless nested files match), into drafts."""
    if path.is_dir():
        files = sorted(
            p
            for p in path.rglob("*")
            if p.is_file() and p.suffix.lower() in _TEXT_SUFFIXES | _JSON_SUFFIXES
        )
        if not files:
            raise LoaderError(f"no draft files (*.md, *.txt, *.json, *.jsonl) found in {path}")
        drafts: list[Draft] = []
        for file in files:
            drafts.extend(load_file(file))
        return drafts
    if path.is_file():
        return load_file(path)
    raise LoaderError(f"path does not exist: {path}")


def load_file(path: Path) -> list[Draft]:
    suffix = path.suffix.lower()
    try:
        text = path.read_text("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise LoaderError(f"cannot read {path}: {exc}") from exc
    if suffix in _TEXT_SUFFIXES:
        return [_parse_markdown(text, path)]
    if suffix == ".json":
        return _parse_json(text, path)
    if suffix == ".jsonl":
        return _parse_jsonl(text, path)
    raise LoaderError(f"unsupported draft format {suffix!r}: {path}")


def _build_draft(record: dict[str, Any], path: Path, fallback_id: str) -> Draft:
    record.setdefault("id", fallback_id)
    record.setdefault("source", str(path))
    try:
        return Draft.model_validate(record)
    except ValidationError as exc:
        raise LoaderError(f"invalid draft in {path}: {exc}") from exc


def _parse_markdown(text: str, path: Path) -> Draft:
    meta: dict[str, Any] = {}
    body = text
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        closing = next(
            (index for index in range(1, len(lines)) if lines[index].strip() == "---"), None
        )
        if closing is None:
            raise LoaderError(f"unterminated front-matter block in {path}")
        meta = _parse_front_matter("\n".join(lines[1:closing]), path)
        body = "\n".join(lines[closing + 1 :])
    meta["body"] = body.strip()
    return _build_draft(meta, path, fallback_id=path.stem)


def _parse_front_matter(block: str, path: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for line_number, raw_line in enumerate(block.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition(":")
        key = key.strip()
        if not separator or not key:
            raise LoaderError(
                f"{path}: front-matter line {line_number} is not 'key: value': {raw_line!r}"
            )
        if key not in _FRONT_MATTER_KEYS:
            allowed = ", ".join(sorted(_FRONT_MATTER_KEYS))
            raise LoaderError(f"{path}: unknown front-matter key {key!r} (allowed: {allowed})")
        meta[key] = value.strip().strip("'\"")
    return meta


def _parse_json(text: str, path: Path) -> list[Draft]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LoaderError(f"invalid JSON in {path}: {exc}") from exc
    records = data if isinstance(data, list) else [data]
    drafts: list[Draft] = []
    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise LoaderError(f"{path}: draft #{index + 1} is not an object")
        drafts.append(_build_draft(dict(record), path, fallback_id=f"{path.stem}-{index + 1}"))
    return drafts


def _parse_jsonl(text: str, path: Path) -> list[Draft]:
    drafts: list[Draft] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise LoaderError(f"invalid JSON on line {line_number} of {path}: {exc}") from exc
        if not isinstance(record, dict):
            raise LoaderError(f"{path}: line {line_number} is not an object")
        drafts.append(_build_draft(dict(record), path, fallback_id=f"{path.stem}-{line_number}"))
    if not drafts:
        raise LoaderError(f"no drafts found in {path}")
    return drafts
