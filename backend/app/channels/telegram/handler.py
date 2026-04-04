from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.runtime.factory import RuntimeFactory
from app.schemas.agent import AgentDesign

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter()

_runtimes: dict[str, object] = {}
_designs:  dict[str, AgentDesign] = {}


def register_design(agent_id: str, design: AgentDesign) -> None:
    _designs[agent_id] = design


@router.post("/telegram/webhook/{agent_id}")
async def telegram_webhook(agent_id: str, request: Request) -> dict:
    """
    Webhook del Bot API de Telegram.
    Recibe updates como JSON.
    """
    update = await request.json()

    # Extraer mensaje de texto del update
    message = update.get("message") or update.get("edited_message")
    if not message:
        return {"ok": True}  # Ignorar otros tipos de update

    chat_id     = message["chat"]["id"]
    user_text   = message.get("text", "").strip()
    message_id  = message.get("message_id")

    if not user_text or user_text.startswith("/"):
        if user_text == "/start":
            await _send_telegram(chat_id, "¡Hola! Soy tu asistente IA. ¿En qué puedo ayudarte?")
        return {"ok": True}

    logger.info(f"[TELEGRAM] chat_id={chat_id} agent={agent_id}: {user_text[:80]}")

    # Mostrar "escribiendo..." mientras el agente procesa
    await _send_chat_action(chat_id, "typing")

    # Construir runtime si no existe
    if agent_id not in _runtimes:
        if agent_id not in _designs:
            await _send_telegram(chat_id, "Este agente no está disponible.")
            return {"ok": True}
        _runtimes[agent_id] = RuntimeFactory().build(_designs[agent_id])

    runtime = _runtimes[agent_id]
    session_id = f"telegram_{chat_id}_{agent_id}"

    try:
        response = await runtime.invoke(user_text, session_id)
        reply = response.output

        # Telegram soporta Markdown — enviamos con parse_mode
        await _send_telegram(
            chat_id, reply,
            reply_to_message_id=message_id,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.error(f"[TELEGRAM] Error: {e}")
        await _send_telegram(chat_id, "Ocurrió un error. Por favor intentá nuevamente.")

    return {"ok": True}


async def _send_telegram(
    chat_id: int,
    text: str,
    reply_to_message_id: int | None = None,
    parse_mode: str | None = None,
) -> None:
    if not settings.telegram_bot_token:
        logger.warning("[TELEGRAM] Bot token no configurado")
        return

    import httpx
    payload: dict = {"chat_id": chat_id, "text": text[:4096]}
    if reply_to_message_id:
        payload["reply_to_message_id"] = reply_to_message_id
    if parse_mode:
        payload["parse_mode"] = parse_mode

    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
            json=payload,
        )


async def _send_chat_action(chat_id: int, action: str = "typing") -> None:
    if not settings.telegram_bot_token:
        return
    import httpx
    async with httpx.AsyncClient(timeout=5.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendChatAction",
            json={"chat_id": chat_id, "action": action},
        )
