from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request, Response

from app.core.config import get_settings
from app.runtime.factory import RuntimeFactory
from app.schemas.agent import AgentDesign

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter()

# Caché simple de runtimes por agent_id (Sprint 4: Redis + DB lookup)
_runtimes: dict[str, object] = {}
_designs:  dict[str, AgentDesign] = {}


def register_design(agent_id: str, design: AgentDesign) -> None:
    """Registra el design de un agente para que el canal pueda usarlo."""
    _designs[agent_id] = design


@router.post("/whatsapp/webhook/{agent_id}")
async def whatsapp_webhook(agent_id: str, request: Request) -> Response:
    """
    Webhook de Twilio para WhatsApp.
    Twilio envía el mensaje como form data (application/x-www-form-urlencoded).
    """
    # 1. Validar firma Twilio
    body = await request.body()
    if not _validate_twilio_signature(request, body):
        raise HTTPException(403, "Firma Twilio inválida")

    # 2. Parsear payload
    form = parse_qs(body.decode())
    user_message = form.get("Body", [""])[0].strip()
    from_number  = form.get("From", [""])[0]   # "whatsapp:+549..."
    to_number    = form.get("To",   [""])[0]   # nuestro número de Twilio

    if not user_message:
        return _twiml_response("")

    logger.info(f"[WHATSAPP] {from_number} → agent={agent_id}: {user_message[:80]}")

    # 3. Obtener o construir el runtime
    if agent_id not in _runtimes:
        if agent_id not in _designs:
            logger.error(f"[WHATSAPP] Design no encontrado para agent_id={agent_id}")
            return _twiml_response("Lo siento, este agente no está disponible en este momento.")
        design = _designs[agent_id]
        _runtimes[agent_id] = RuntimeFactory().build(design)

    runtime = _runtimes[agent_id]

    # 4. session_id basado en número de origen (memoria por usuario)
    session_id = f"whatsapp_{from_number.replace('+', '').replace(':', '_')}_{agent_id}"

    # 5. Invocar agente (WhatsApp no soporta streaming, respuesta completa)
    try:
        response = await runtime.invoke(user_message, session_id)
        reply_text = response.output

        # WhatsApp tiene límite de 1600 caracteres por mensaje
        if len(reply_text) > 1600:
            reply_text = reply_text[:1570] + "...\n\n_(Respuesta truncada)_"

    except Exception as e:
        logger.error(f"[WHATSAPP] Error en invocación: {e}")
        reply_text = "Ocurrió un error procesando tu mensaje. Por favor intentá nuevamente."

    # 6. Responder via TwiML
    return _twiml_response(reply_text)


@router.get("/whatsapp/webhook/{agent_id}")
async def whatsapp_verify(request: Request) -> dict:
    """Verificación inicial del webhook (GET de Twilio)."""
    return {"status": "ok", "agent_id": request.path_params.get("agent_id")}


def _validate_twilio_signature(request: Request, body: bytes) -> bool:
    """Valida que el request viene realmente de Twilio."""
    if not settings.twilio_auth_token:
        return True  # Skip en dev sin credenciales

    twilio_signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)

    # Reconstruir firma esperada
    form_data = parse_qs(body.decode())
    sorted_params = "".join(
        f"{k}{v[0]}"
        for k, v in sorted(form_data.items())
    )
    expected = hmac.new(
        settings.twilio_auth_token.encode(),
        (url + sorted_params).encode(),
        hashlib.sha1,
    ).digest()

    import base64
    expected_b64 = base64.b64encode(expected).decode()
    return hmac.compare_digest(twilio_signature, expected_b64)


def _twiml_response(message: str) -> Response:
    """Genera respuesta TwiML para WhatsApp."""
    safe_msg = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Message>{safe_msg}</Message>
</Response>"""
    return Response(content=twiml, media_type="application/xml")
