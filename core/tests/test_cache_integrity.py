from __future__ import annotations

import os

from aura_core.diagnostics import CacheManifestStore, compute_sha256, verify_and_repair


def _write(path: str, content: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(content)


def test_a_file_seen_for_the_first_time_is_trusted_not_flagged_as_corrupt(tmp_path):
    model_path = str(tmp_path / "model.onnx")
    _write(model_path, b"fake model bytes")
    manifest = CacheManifestStore(str(tmp_path / "manifest.json"))

    issues = verify_and_repair([model_path], manifest)

    assert issues[0].status == "trusted_new"
    assert manifest.get(os.path.abspath(model_path)) == compute_sha256(model_path)


def test_an_unchanged_file_is_reported_ok_on_a_second_check(tmp_path):
    model_path = str(tmp_path / "model.onnx")
    _write(model_path, b"fake model bytes")
    manifest = CacheManifestStore(str(tmp_path / "manifest.json"))
    verify_and_repair([model_path], manifest)

    issues = verify_and_repair([model_path], manifest)

    assert issues[0].status == "ok"
    assert os.path.exists(model_path)  # untouched


def test_a_missing_file_is_reported_missing_not_corrupted(tmp_path):
    manifest = CacheManifestStore(str(tmp_path / "manifest.json"))

    issues = verify_and_repair([str(tmp_path / "does_not_exist.onnx")], manifest)

    assert issues[0].status == "missing"


def test_a_file_that_changes_after_being_trusted_is_quarantined_not_deleted(tmp_path):
    model_path = str(tmp_path / "model.onnx")
    _write(model_path, b"original good bytes")
    manifest = CacheManifestStore(str(tmp_path / "manifest.json"))
    verify_and_repair([model_path], manifest)  # first trust

    _write(model_path, b"corrupted!! different bytes entirely")  # simulate on-disk corruption

    quarantine_dir = str(tmp_path / "quarantine")
    issues = verify_and_repair([model_path], manifest, quarantine_dir=quarantine_dir)

    assert issues[0].status == "corrupted_and_quarantined"
    assert not os.path.exists(model_path)  # never silently left in place
    quarantined_files = os.listdir(quarantine_dir)
    assert len(quarantined_files) == 1
    with open(os.path.join(quarantine_dir, quarantined_files[0]), "rb") as handle:
        assert handle.read() == b"corrupted!! different bytes entirely"  # the bad bytes are preserved, not lost


def test_a_quarantined_file_is_re_trusted_fresh_if_a_new_copy_appears_later(tmp_path):
    model_path = str(tmp_path / "model.onnx")
    _write(model_path, b"original good bytes")
    manifest = CacheManifestStore(str(tmp_path / "manifest.json"))
    verify_and_repair([model_path], manifest)
    _write(model_path, b"corrupted!!")
    verify_and_repair([model_path], manifest, quarantine_dir=str(tmp_path / "quarantine"))

    _write(model_path, b"freshly re-downloaded good bytes")  # owner re-ran the RUNBOOK download step
    issues = verify_and_repair([model_path], manifest)

    assert issues[0].status == "trusted_new"
