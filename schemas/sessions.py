"""
Schémas Pydantic pour la gestion des sessions conversationnelles.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class ConversationState(str, Enum):
    """États possibles de la conversation."""
    GREETING = "GREETING"
    BROWSING = "BROWSING"
    ADDING_TO_CART = "ADDING_TO_CART"
    REVIEWING_CART = "REVIEWING_CART"
    CONFIRMING_ORDER = "CONFIRMING_ORDER"
    ORDER_PLACED = "ORDER_PLACED"
    TRACKING = "TRACKING"
    HELP = "HELP"
    UNKNOWN = "UNKNOWN"


class HistoryEntry(BaseModel):
    """Entrée dans l'historique de conversation."""
    role: str = Field(..., description="'user' ou 'assistant'")
    content: str = Field(..., description="Contenu du message")
    timestamp: datetime = Field(default_factory=datetime.now)


class ConversationSession(BaseModel):
    """Session de conversation d'un utilisateur."""
    phone_number: str = Field(..., description="Numéro WhatsApp de l'utilisateur")
    state: ConversationState = Field(default=ConversationState.UNKNOWN)
    client_id: Optional[int] = Field(None, description="ID client Selfcare")
    client_name: Optional[str] = Field(None, description="Nom du client")
    cart: Dict[str, Any] = Field(default_factory=dict, description="Panier sérialisé")
    pending_product: Optional[str] = Field(None, description="Code produit en attente de quantité")
    history: List[Dict[str, str]] = Field(default_factory=list, description="Historique de conversation")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def add_message(self, role: str, content: str, max_history: int = 5) -> None:
        """Ajoute un message à l'historique en respectant la limite."""
        self.history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        })
        # Garder seulement les N derniers messages
        if len(self.history) > max_history * 2:
            self.history = self.history[-(max_history * 2):]
        self.updated_at = datetime.now()

    def get_context(self) -> Dict[str, Any]:
        """Retourne le contexte de la session pour les agents CrewAI."""
        return {
            "phone_number": self.phone_number,
            "state": self.state.value,
            "client_id": self.client_id,
            "client_name": self.client_name,
            "cart": self.cart,
            "history": self.history,
        }

    def to_redis_dict(self) -> Dict[str, Any]:
        """Sérialise la session pour stockage Redis."""
        return self.model_dump(mode="json")

    @classmethod
    def from_redis_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        """Désérialise la session depuis Redis."""
        return cls.model_validate(data)
