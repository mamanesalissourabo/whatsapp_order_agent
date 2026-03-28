"""
Outil pour l'envoi de messages WhatsApp via l'API Meta.
"""

from config.settings import settings
import httpx
import logging

logger = logging.getLogger(__name__)


async def send_whatsapp_message(to: str, message: str) -> dict:
    """
    Fonction utilitaire async pour envoyer un message WhatsApp.
    Utilisée directement dans le webhook (hors contexte CrewAI).
    
    Args:
        to: Numéro de téléphone du destinataire
        message: Texte du message
        
    Returns:
        Dictionnaire avec le résultat de l'envoi
    """
    logger.info(f"📤 Envoi async WhatsApp à {to}")

    try:
        url = (
            f"{settings.whatsapp_api_url}/"
            f"{settings.whatsapp_phone_number_id}/messages"
        )

        headers = {
            "Authorization": f"Bearer {settings.whatsapp_access_token}",
            "Content-Type": "application/json",
        }

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": message},
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()

        message_id = result.get("messages", [{}])[0].get("id", "unknown")
        logger.info(f"✅ Message envoyé. ID: {message_id}")

        return {"success": True, "message_id": message_id}

    except Exception as e:
        logger.error(f"❌ Erreur envoi WhatsApp: {e}")
        return {"success": False, "error": str(e)}
