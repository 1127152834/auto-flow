import hashlib
from pathlib import Path

import pytest

from autoflow.domain.projects.models import ProjectError
from autoflow.infrastructure.filesystem import project_excel as excel


def test_export_records_evidence_before_target_becomes_visible(tmp_path: Path):
    target = tmp_path / "result.xlsx"
    evidence = []

    def persist(publication):
        assert not target.exists()
        evidence.append(publication)

    result = excel.write_workbook(
        target, ["编号"], [["001"], ["=1+1"]], before_publish=persist
    )
    assert result == evidence[0]
    assert result.record_count == 2
    assert result.size_bytes == target.stat().st_size
    assert result.sha256 == hashlib.sha256(target.read_bytes()).hexdigest()
    assert excel.verify_workbook_publication(target, result.sha256) == "matches"


def test_failed_evidence_commit_does_not_publish(tmp_path: Path):
    target = tmp_path / "result.xlsx"

    def persist(_):
        raise RuntimeError("database unavailable")

    with pytest.raises(RuntimeError, match="database unavailable"):
        excel.write_workbook(target, ["编号"], [["001"]], before_publish=persist)
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_lost_publication_result_can_be_verified_without_writing_again(
    tmp_path: Path, monkeypatch
):
    target = tmp_path / "result.xlsx"
    link = excel.os.link
    evidence = []

    def lose_response(source, destination):
        link(source, destination)
        raise OSError("interrupted after publication")

    monkeypatch.setattr(excel.os, "link", lose_response)
    with pytest.raises(ProjectError):
        excel.write_workbook(
            target, ["编号"], [["001"]], before_publish=evidence.append
        )
    assert excel.verify_workbook_publication(target, evidence[0].sha256) == "matches"
    before = target.read_bytes()
    assert excel.verify_workbook_publication(target, "0" * 64) == "conflict"
    assert target.read_bytes() == before
    assert (
        excel.verify_workbook_publication(tmp_path / "missing.xlsx", evidence[0].sha256)
        == "missing"
    )


def test_verification_does_not_follow_replaced_target_symlinks(tmp_path: Path):
    source = tmp_path / "source.xlsx"
    source.write_bytes(b"private")
    target = tmp_path / "result.xlsx"
    target.symlink_to(source)
    assert (
        excel.verify_workbook_publication(
            target, hashlib.sha256(b"private").hexdigest()
        )
        == "conflict"
    )
