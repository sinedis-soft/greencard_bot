import shutil
from pathlib import Path


def remove_request_storage(storage_base_path: Path, request_id: str) -> bool:
    request_path = (storage_base_path / request_id).resolve()
    storage_root = storage_base_path.resolve()
    if storage_root not in request_path.parents or not request_path.exists() or not request_path.is_dir():
        return False
    shutil.rmtree(request_path)
    return True
