from app.services.data_retention_service import DataRetentionService


def run_data_retention() -> dict:
    service = DataRetentionService()
    old_operational_data = service.cleanup_old_operational_data()
    return {
        "application_file_dirs_deleted": service.cleanup_transferred_application_files(),
        **old_operational_data,
    }
