from __future__ import annotations

import logging
import time

from app.services.reminder_service import ReminderService

logger = logging.getLogger(__name__)


def run_reminder_checks(limit: int = 100) -> dict[str, int]:
    """Process pending reminder tasks that are due now."""
    stats = ReminderService().process_due(limit=limit)
    logger.info("reminder_worker processed reminders stats=%s", stats)
    return stats


def run_forever(interval_seconds: int = 60, limit: int = 100) -> None:
    while True:
        try:
            run_reminder_checks(limit=limit)
        except Exception:  # pragma: no cover - worker safety net
            logger.exception("reminder_worker failed")
        time.sleep(interval_seconds)


if __name__ == "__main__":
    run_forever()
