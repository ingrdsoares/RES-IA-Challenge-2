import logging
import smtplib
import ssl
from email.errors import HeaderParseError
from email.headerregistry import Address
from email.message import EmailMessage

from app.access.service import RESET_MINUTES
from app.config import Settings

logger = logging.getLogger(__name__)


def deliver(settings: Settings, to: str, subject: str, body: str):
    message = EmailMessage()
    message["From"] = Address("Sócio Digital", addr_spec=settings.smtp_from)
    message["To"] = Address(addr_spec=to)
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_starttls:
            smtp.starttls(context=ssl.create_default_context())
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(message, from_addr=settings.smtp_from, to_addrs=[to])


def send_reset_link(settings: Settings, email: str, secret: str):
    try:
        link = f"{settings.frontend_url}#redefinir-senha?token={secret}"
        deliver(
            settings,
            email,
            "Redefina sua senha no Sócio Digital",
            f"Para criar uma nova senha, abra este link em até {RESET_MINUTES} minutos:\n\n"
            f"{link}\n\nSe você não pediu a alteração, pode ignorar esta mensagem.",
        )
    except (OSError, HeaderParseError, ValueError):
        # SMTP e erros de endereçamento podem conter dados privados.
        logger.error("Falha na entrega do e-mail de recuperação de senha.")
