"""
Schémas Pydantic pour les messages WhatsApp.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class MessageType(str, Enum):
    """Types de messages WhatsApp supportés."""
    TEXT = "text"
    IMAGE = "image"
    DOCUMENT = "document"
    INTERACTIVE = "interactive"
    BUTTON = "button"


class WhatsAppContact(BaseModel):
    """Contact WhatsApp extrait du webhook."""
    wa_id: str = Field(..., description="Numéro WhatsApp de l'expéditeur")
    profile_name: Optional[str] = Field(None, description="Nom de profil WhatsApp")


class WhatsAppTextMessage(BaseModel):
    """Contenu d'un message texte."""
    body: str = Field(..., description="Texte du message")


class WhatsAppMessage(BaseModel):
    """Message WhatsApp reçu via webhook."""
    message_id: str = Field(..., alias="id", description="ID unique du message")
    from_number: str = Field(..., alias="from", description="Numéro de l'expéditeur")
    timestamp: str = Field(..., description="Timestamp du message")
    type: MessageType = Field(default=MessageType.TEXT, description="Type de message")
    text: Optional[WhatsAppTextMessage] = None

    model_config = {"populate_by_name": True}

    @property
    def body(self) -> str:
        """Retourne le corps du message texte."""
        if self.text:
            return self.text.body
        return ""


class WhatsAppWebhookPayload(BaseModel):
    """Payload complet du webhook WhatsApp Meta."""
    object: str = Field(default="whatsapp_business_account")
    entry: List[Dict[str, Any]] = Field(default_factory=list)

    def extract_messages(self) -> List[Dict[str, Any]]:
        """
        Extrait les messages du payload webhook.
        
        Returns:
            Liste de dictionnaires avec phone_number, message_text, message_id, profile_name
        """
        messages = []
        for entry in self.entry:
            changes = entry.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                contacts = value.get("contacts", [])
                raw_messages = value.get("messages", [])

                contact_map = {
                    c.get("wa_id"): c.get("profile", {}).get("name", "")
                    for c in contacts
                }

                for msg in raw_messages:
                    phone = msg.get("from", "")
                    msg_type = msg.get("type", "")
                    
                    if msg_type == "text":
                        messages.append({
                            "phone_number": phone,
                            "message_text": msg.get("text", {}).get("body", ""),
                            "message_type": "text",
                            "message_id": msg.get("id", ""),
                            "profile_name": contact_map.get(phone, ""),
                            "timestamp": msg.get("timestamp", ""),
                        })
                    elif msg_type == "audio":
                        messages.append({
                            "phone_number": phone,
                            "message_text": "",
                            "message_type": "audio",
                            "media_id": msg.get("audio", {}).get("id", ""),
                            "message_id": msg.get("id", ""),
                            "profile_name": contact_map.get(phone, ""),
                            "timestamp": msg.get("timestamp", ""),
                        })
        return messages


class WhatsAppSendMessage(BaseModel):
    """Message à envoyer via l'API WhatsApp."""
    to: str = Field(..., description="Numéro de téléphone destinataire")
    text: str = Field(..., description="Texte du message à envoyer")
    reply_to_message_id: Optional[str] = Field(None, description="ID du message auquel répondre")
