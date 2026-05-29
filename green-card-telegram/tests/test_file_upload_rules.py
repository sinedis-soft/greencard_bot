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


def test_bitrix_file_service_updates_multiple_deal_files_as_filedata(tmp_path: Path):
    from app.services.bitrix_file_service import BITRIX_DEAL_VEHICLE_DOCS_FIELD, BitrixFileService
    from app.services.bitrix24_client import Bitrix24Client

    calls = []

    class Client(Bitrix24Client):
        def _post(self, method, payload):
            calls.append((method, payload))
            return {"result": True}

    first = tmp_path / "front.pdf"
    second = tmp_path / "back.pdf"
    first.write_bytes(b"front")
    second.write_bytes(b"back")

    file_ids = BitrixFileService(Client("https://example.test/rest")).upload_and_attach_files_to_deal(55, [str(first), str(second)])

    assert file_ids == ["deal:55:front.pdf", "deal:55:back.pdf"]
    assert calls == [
        (
            "crm.deal.update",
            {
                "id": 55,
                "fields": {
                    BITRIX_DEAL_VEHICLE_DOCS_FIELD: [
                        {"fileData": ["front.pdf", "ZnJvbnQ="]},
                        {"fileData": ["back.pdf", "YmFjaw=="]},
                    ]
                },
            },
        )
    ]


def test_bitrix_client_flattens_crm_filedata_with_positional_indexes():
    from app.services.bitrix24_client import Bitrix24Client
    from app.services.bitrix_file_service import BITRIX_DEAL_VEHICLE_DOCS_FIELD

    payload = {
        "fields": {
            BITRIX_DEAL_VEHICLE_DOCS_FIELD: [
                {"fileData": ["front.pdf", "ZnJvbnQ="]},
                {"fileData": ["back.pdf", "YmFjaw=="]},
            ]
        }
    }

    assert Bitrix24Client("https://example.test/rest")._flatten_payload(payload) == [
        (f"fields[{BITRIX_DEAL_VEHICLE_DOCS_FIELD}][0][fileData][0]", "front.pdf"),
        (f"fields[{BITRIX_DEAL_VEHICLE_DOCS_FIELD}][0][fileData][1]", "ZnJvbnQ="),
        (f"fields[{BITRIX_DEAL_VEHICLE_DOCS_FIELD}][1][fileData][0]", "back.pdf"),
        (f"fields[{BITRIX_DEAL_VEHICLE_DOCS_FIELD}][1][fileData][1]", "YmFjaw=="),
    ]
