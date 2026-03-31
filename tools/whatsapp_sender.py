"""
Outil pour l'envoi de messages WhatsApp via l'API Meta.
Supporte : texte simple, listes interactives, boutons de réponse.
"""

from config.settings import settings
import httpx
import logging

logger = logging.getLogger(__name__)


def _get_url() -> str:
    return f"{settings.whatsapp_api_url}/{settings.whatsapp_phone_number_id}/messages"


def _get_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.whatsapp_access_token}",
        "Content-Type": "application/json",
    }


async def _send_payload(to: str, payload: dict) -> dict:
    """Envoi générique d'un payload WhatsApp."""
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(_get_url(), headers=_get_headers(), json=payload)
            response.raise_for_status()
            result = response.json()

        message_id = result.get("messages", [{}])[0].get("id", "unknown")
        logger.info(f"✅ Message envoyé. ID: {message_id}")
        return {"success": True, "message_id": message_id}

    except Exception as e:
        logger.error(f"❌ Erreur envoi WhatsApp: {e}")
        return {"success": False, "error": str(e)}


async def send_whatsapp_message(to: str, message: str) -> dict:
    """
    Envoie un message texte simple via WhatsApp.
    """
    logger.info(f"📤 Envoi texte WhatsApp à {to}")
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message},
    }
    return await _send_payload(to, payload)


async def send_whatsapp_interactive_list(
    to: str,
    body: str,
    button_text: str,
    sections: list[dict],
    header: str = "",
    footer: str = "",
) -> dict:
    """
    Envoie un message interactif de type liste.

    Args:
        to: Numéro destinataire
        body: Texte principal (max 1024 chars)
        button_text: Texte du bouton d'ouverture (max 20 chars)
        sections: Liste de sections, chaque section = {
            "title": str (max 24 chars),
            "rows": [{"id": str, "title": str (max 24), "description": str (max 72)}]
        }
        header: Texte d'en-tête optionnel (max 60 chars)
        footer: Texte de pied optionnel (max 60 chars)
    """
    logger.info(f"📤 Envoi liste interactive WhatsApp à {to}")

    interactive = {
        "type": "list",
        "body": {"text": body[:1024]},
        "action": {
            "button": button_text[:20],
            "sections": sections,
        },
    }
    if header:
        interactive["header"] = {"type": "text", "text": header[:60]}
    if footer:
        interactive["footer"] = {"text": footer[:60]}

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
    return await _send_payload(to, payload)


async def send_whatsapp_buttons(
    to: str,
    body: str,
    buttons: list[dict],
    header: str = "",
    footer: str = "",
) -> dict:
    """
    Envoie un message interactif avec boutons de réponse (max 3).

    Args:
        to: Numéro destinataire
        body: Texte principal
        buttons: Liste de boutons [{"id": str, "title": str (max 20 chars)}]
        header: Texte d'en-tête optionnel
        footer: Texte de pied optionnel
    """
    logger.info(f"📤 Envoi boutons WhatsApp à {to}")

    btn_list = []
    for b in buttons[:3]:
        btn_list.append({
            "type": "reply",
            "reply": {"id": b["id"], "title": b["title"][:20]},
        })

    interactive = {
        "type": "button",
        "body": {"text": body[:1024]},
        "action": {"buttons": btn_list},
    }
    if header:
        interactive["header"] = {"type": "text", "text": header[:60]}
    if footer:
        interactive["footer"] = {"text": footer[:60]}

    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "interactive",
        "interactive": interactive,
    }
    return await _send_payload(to, payload)
