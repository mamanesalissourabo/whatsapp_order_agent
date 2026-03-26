"""
Outil CrewAI pour l'envoi de messages WhatsApp via l'API Meta.
"""

from crewai.tools import BaseTool
from typing import Type
from pydantic import BaseModel, Field
from config.settings import settings
import httpx
import logging
import json

logger = logging.getLogger(__name__)


class SendWhatsAppInput(BaseModel):
    """Schéma d'entrée pour l'envoi d'un message WhatsApp."""
    to: str = Field(..., description="Numéro de téléphone du destinataire (format international)")
    message: str = Field(..., description="Texte du message à envoyer")


class SendWhatsAppMessageTool(BaseTool):
    """
    Outil pour envoyer un message WhatsApp via l'API Cloud de Meta.
    """
    name: str = "send_whatsapp_message"
    description: str = (
        "Envoie un message texte à un utilisateur via WhatsApp. "
        "Utilise cette outil uniquement quand la réponse finale est prête."
    )
    args_schema: Type[BaseModel] = SendWhatsAppInput

    def _run(self, to: str, message: str) -> str:
        """Envoie un message WhatsApp."""
        logger.info(f"📤 Envoi WhatsApp à {to}: {message[:50]}...")

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

            with httpx.Client(timeout=30) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

            message_id = result.get("messages", [{}])[0].get("id", "unknown")
            logger.info(f"✅ Message envoyé avec succès. ID: {message_id}")

            return json.dumps({
                "success": True,
                "message_id": message_id,
                "status": "sent",
            }, ensure_ascii=False)

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Erreur HTTP WhatsApp: {e.response.status_code} - {e.response.text}")
            return json.dumps({
                "success": False,
                "error": f"Erreur API WhatsApp: {e.response.status_code}",
                "details": e.response.text,
            }, ensure_ascii=False)

        except Exception as e:
            logger.error(f"❌ Erreur envoi WhatsApp: {e}")
            return json.dumps({
                "success": False,
                "error": str(e),
            }, ensure_ascii=False)


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
