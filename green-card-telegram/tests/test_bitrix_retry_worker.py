from app.services.bitrix_sync_service import BitrixSyncService


def test_create_job_smoke(monkeypatch):
    # smoke: method exists
    svc = BitrixSyncService()
    assert hasattr(svc, 'create_job')


def test_retry_status_methods_exist():
    svc = BitrixSyncService()
    assert hasattr(svc, 'mark_retrying')
    assert hasattr(svc, 'mark_success')
