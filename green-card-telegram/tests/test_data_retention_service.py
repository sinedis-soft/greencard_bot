from app.services.storage_cleanup import remove_request_storage


def test_remove_request_storage_deletes_only_request_directory(tmp_path):
    storage_root = tmp_path / "storage" / "applications"
    request_dir = storage_root / "req-1" / "vehicle-1"
    request_dir.mkdir(parents=True)
    (request_dir / "passport.pdf").write_bytes(b"file")

    assert remove_request_storage(storage_root, "req-1") is True
    assert not (storage_root / "req-1").exists()
    assert storage_root.exists()


def test_remove_request_storage_ignores_missing_directory(tmp_path):
    assert remove_request_storage(tmp_path, "missing") is False
