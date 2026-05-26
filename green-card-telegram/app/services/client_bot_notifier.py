from app.services.operator_notifier_service import ClientNotifierService
from app.services.operator_ticket_service import OperatorTicketService


def notify_client_operator_connected(request_id: str) -> None:
    ticket = OperatorTicketService().get_ticket(request_id)
    if not ticket or not ticket.telegram_user_id:
        return
    ClientNotifierService().send_to_client(ticket.telegram_user_id, "Оператор подключился")
