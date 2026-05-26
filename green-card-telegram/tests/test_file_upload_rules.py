from pathlib import Path

from app.services.file_storage_service import FileStorageService, FileValidationError


def test_jpg_passes(tmp_path: Path):
    s = FileStorageService(tmp_path)
    s.validate("image/jpeg", 1024)


def test_png_passes(tmp_path: Path):
    s = FileStorageService(tmp_path)
    s.validate("image/png", 1024)


def test_pdf_passes(tmp_path: Path):
    s = FileStorageService(tmp_path)
    s.validate("application/pdf", 1024)


def test_exe_rejected(tmp_path: Path):
    s = FileStorageService(tmp_path)
    try:
        s.validate("application/x-msdownload", 1024)
        assert False
    except FileValidationError:
        assert True


def test_too_large_rejected(tmp_path: Path):
    s = FileStorageService(tmp_path)
    try:
        s.validate("application/pdf", 11 * 1024 * 1024)
        assert False
    except FileValidationError:
        assert True


def test_local_save_when_bitrix_unavailable(tmp_path: Path):
    s = FileStorageService(tmp_path)
    p = s.save_file("req", 1, "a.pdf", b"x")
    assert p.exists()
