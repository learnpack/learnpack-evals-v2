"""bump-instrument: textual clone of an instrument YAML into the next draft version.

The transformation is deliberately textual — header comments and block-scalar style are
part of the authored artifact and a parse/dump round-trip would destroy them. These
tests pin that property, the self-check, and every refusal path.
"""

import yaml
from test_instrument_authoring_api import import_spec, spec

from app.cli import run_bump_instrument

SOURCE_TEMPLATE = """\
# {iid} v1 — DRAFT for team review.
# Publish with: python -m app.cli publish-instrument --id {iid}-v1

instrument_id: {iid}
version: {version}
name: "Bump test"
purpose: >
  Internal QA of generated courses: a minimal
  instrument for bump tests.

bindings:
  - package_format: LearnpackV1
"""


def write_source(tmp_path, iid: str, version: str = "v1"):
    source = tmp_path / f"{iid}-{version}.yaml"
    source.write_text(SOURCE_TEMPLATE.format(iid=iid, version=version), encoding="utf-8")
    return source


def test_bump_writes_next_version_preserving_comments_and_style(tmp_path, unique):
    iid = f"qa-bump-{unique}"
    source = write_source(tmp_path, iid)
    original = source.read_text(encoding="utf-8")

    assert run_bump_instrument(source, None, None) == 0

    target = tmp_path / f"{iid}-v2.yaml"
    text = target.read_text(encoding="utf-8")
    assert f"# {iid} v1 — DRAFT for team review." in text  # comments survive verbatim
    assert "purpose: >\n  Internal QA of generated courses: a minimal\n" in text
    parsed = yaml.safe_load(text)
    assert parsed["instrument_id"] == iid
    assert parsed["version"] == "v2"
    assert source.read_text(encoding="utf-8") == original  # the source is untouched


def test_bump_inserts_reason_yaml_escaped(tmp_path, unique):
    source = write_source(tmp_path, f"qa-bump-{unique}")
    reason = 'tighten "arc" criteria'

    assert run_bump_instrument(source, None, reason) == 0

    parsed = yaml.safe_load((tmp_path / f"qa-bump-{unique}-v2.yaml").read_text(encoding="utf-8"))
    assert parsed["revision_reason"] == reason


def test_bump_replaces_existing_block_scalar_reason(tmp_path, unique):
    iid = f"qa-bump-{unique}"
    source = write_source(tmp_path, iid)
    source.write_text(
        source.read_text(encoding="utf-8")
        + "revision_reason: >\n  the old reason, spanning\n  two indented lines\n",
        encoding="utf-8",
    )

    assert run_bump_instrument(source, None, "new reason") == 0

    text = (tmp_path / f"{iid}-v2.yaml").read_text(encoding="utf-8")
    assert "old reason" not in text  # no orphaned continuation lines
    assert yaml.safe_load(text)["revision_reason"] == "new reason"


def test_bump_requires_to_when_version_scheme_unknown(tmp_path, unique, capsys):
    iid = f"qa-bump-{unique}"
    source = write_source(tmp_path, iid, version="2024.1")

    assert run_bump_instrument(source, None, None) == 1
    assert "--to" in capsys.readouterr().err

    assert run_bump_instrument(source, "v9", None) == 0
    assert (tmp_path / f"{iid}-v9.yaml").exists()


def test_bump_rejects_same_version_and_bad_to(tmp_path, unique, capsys):
    source = write_source(tmp_path, f"qa-bump-{unique}")

    assert run_bump_instrument(source, "v1", None) == 1
    assert "equals the current one" in capsys.readouterr().err

    assert run_bump_instrument(source, "v2/x", None) == 1
    assert "invalid target version" in capsys.readouterr().err


def test_bump_refuses_existing_target_file(tmp_path, unique):
    iid = f"qa-bump-{unique}"
    source = write_source(tmp_path, iid)
    target = tmp_path / f"{iid}-v2.yaml"
    target.write_text("sentinel", encoding="utf-8")

    assert run_bump_instrument(source, None, None) == 1
    assert target.read_text(encoding="utf-8") == "sentinel"  # never overwritten


def test_bump_refuses_when_target_version_exists_in_db(tmp_path, cleanup, unique, capsys):
    import_spec(cleanup, spec(unique, version="v2"))  # occupies qa-{unique}-v2 in the db
    source = write_source(tmp_path, f"qa-{unique}")

    assert run_bump_instrument(source, None, None) == 1
    assert f"qa-{unique}-v2" in capsys.readouterr().err
    assert not (tmp_path / f"qa-{unique}-v2.yaml").exists()


def test_bump_reports_source_status_and_next_steps(tmp_path, cleanup, unique, capsys):
    import_spec(cleanup, spec(unique))  # qa-{unique}-v1 imported as draft
    source = write_source(tmp_path, f"qa-{unique}")

    assert run_bump_instrument(source, None, None) == 0
    out = capsys.readouterr().out
    assert f"source qa-{unique}-v1 in db: draft" in out
    assert "import-instrument" in out
    assert f"publish-instrument --id qa-{unique}-v2" in out


def test_bump_errors_cleanly_on_broken_input(tmp_path, unique, capsys):
    missing_version = tmp_path / "no-version.yaml"
    missing_version.write_text(f"instrument_id: qa-bump-{unique}\n", encoding="utf-8")
    assert run_bump_instrument(missing_version, None, None) == 1
    assert "instrument_id/version" in capsys.readouterr().err

    malformed = tmp_path / "malformed.yaml"
    malformed.write_text("instrument_id: [unclosed\n", encoding="utf-8")
    assert run_bump_instrument(malformed, None, None) == 1
    assert "cannot parse" in capsys.readouterr().err
