from sqlalchemy import BigInteger

from app.db.models import AnalyticsEvent, Application, OperatorActionLog, OperatorTicket


def assert_bigint_column(model, column_name: str) -> None:
    assert isinstance(model.__table__.columns[column_name].type, BigInteger)


def test_telegram_and_operator_ids_use_bigint():
    assert_bigint_column(Application, "telegram_user_id")
    assert_bigint_column(OperatorTicket, "telegram_user_id")
    assert_bigint_column(OperatorTicket, "operator_id")
    assert_bigint_column(OperatorActionLog, "operator_id")
    assert_bigint_column(AnalyticsEvent, "telegram_user_id")
