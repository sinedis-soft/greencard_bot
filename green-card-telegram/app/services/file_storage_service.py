from pathlib import Path

ALLOWED_MIME = {"image/jpeg", "image/png", "application/pdf"}
MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_FILES = 10


class FileValidationError(ValueError):
    pass


class FileStorageService:
    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or Path("storage/applications")

    def validate(self, content_type: str, size_bytes: int) -> None:
        if content_type not in ALLOWED_MIME:
            raise FileValidationError("invalid_mime")
        if size_bytes > MAX_FILE_SIZE:
            raise FileValidationError("file_too_large")

    def save_file(self, request_id: str, vehicle_id: int, filename: str, data: bytes) -> Path:
        target_dir = self.base_path / request_id / str(vehicle_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / filename
        target.write_bytes(data)
        return target
