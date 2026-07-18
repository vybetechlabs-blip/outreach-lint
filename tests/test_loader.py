import json
from pathlib import Path

import pytest

from outreach_lint.loader import LoaderError, load_file, load_path

FRONT_MATTER_DOC = """---
id: fm-1
touch: T2
sequence_id: seq-x
hook: the second location
---
Body starts here.

Second paragraph.
"""


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_markdown_with_front_matter(tmp_path: Path) -> None:
    drafts = load_file(_write(tmp_path / "draft.md", FRONT_MATTER_DOC))
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.id == "fm-1"
    assert draft.touch == "T2"
    assert draft.sequence_id == "seq-x"
    assert draft.hook == "the second location"
    assert draft.body == "Body starts here.\n\nSecond paragraph."
    assert draft.source is not None and draft.source.endswith("draft.md")


def test_markdown_without_front_matter_uses_filename_id(tmp_path: Path) -> None:
    drafts = load_file(_write(tmp_path / "plain-note.md", "Just a body.\n"))
    assert drafts[0].id == "plain-note"
    assert drafts[0].body == "Just a body."
    assert drafts[0].touch is None


def test_unknown_front_matter_key_fails_loudly(tmp_path: Path) -> None:
    doc = "---\nsequnce_id: seq-1\n---\nBody.\n"
    with pytest.raises(LoaderError, match="unknown front-matter key 'sequnce_id'"):
        load_file(_write(tmp_path / "typo.md", doc))


def test_unterminated_front_matter_fails(tmp_path: Path) -> None:
    with pytest.raises(LoaderError, match="unterminated front-matter"):
        load_file(_write(tmp_path / "broken.md", "---\ntouch: T1\nBody without closing.\n"))


def test_invalid_touch_value_fails(tmp_path: Path) -> None:
    with pytest.raises(LoaderError, match="invalid draft"):
        load_file(_write(tmp_path / "bad-touch.md", "---\ntouch: T9\n---\nBody.\n"))


def test_json_list_and_single_object(tmp_path: Path) -> None:
    listed = _write(
        tmp_path / "batch.json",
        json.dumps([{"id": "a", "body": "One."}, {"body": "Two.", "touch": "T1"}]),
    )
    drafts = load_file(listed)
    assert [d.id for d in drafts] == ["a", "batch-2"]

    single = _write(tmp_path / "one.json", json.dumps({"body": "Solo."}))
    assert load_file(single)[0].id == "one-1"


def test_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    text = '{"id": "a", "body": "One."}\n\n{"id": "b", "body": "Two."}\n'
    drafts = load_file(_write(tmp_path / "batch.jsonl", text))
    assert [d.id for d in drafts] == ["a", "b"]


def test_malformed_jsonl_reports_line_number(tmp_path: Path) -> None:
    text = '{"id": "a", "body": "One."}\nnot json at all\n'
    with pytest.raises(LoaderError, match="line 2"):
        load_file(_write(tmp_path / "bad.jsonl", text))


def test_non_object_records_fail(tmp_path: Path) -> None:
    with pytest.raises(LoaderError, match="not an object"):
        load_file(_write(tmp_path / "strings.jsonl", '"just a string"\n'))
    with pytest.raises(LoaderError, match="not an object"):
        load_file(_write(tmp_path / "list.json", "[1, 2]"))


def test_directory_loads_all_supported_files(tmp_path: Path) -> None:
    _write(tmp_path / "a.md", "Body a.")
    _write(tmp_path / "b.jsonl", '{"id": "b1", "body": "Body b."}\n')
    _write(tmp_path / "notes.doc", "ignored")
    drafts = load_path(tmp_path)
    assert {d.id for d in drafts} == {"a", "b1"}


def test_empty_directory_fails(tmp_path: Path) -> None:
    with pytest.raises(LoaderError, match="no draft files"):
        load_path(tmp_path)


def test_missing_path_fails(tmp_path: Path) -> None:
    with pytest.raises(LoaderError, match="does not exist"):
        load_path(tmp_path / "nope.md")


def test_unsupported_suffix_fails(tmp_path: Path) -> None:
    with pytest.raises(LoaderError, match="unsupported draft format"):
        load_file(_write(tmp_path / "draft.docx", "whatever"))
