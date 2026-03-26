"""
Gestionnaire de sessions conversationnelles avec Redis.
Stocke l'état de chaque conversation (panier, historique, état).
"""

import redis
import json
import logging
from typing import Optional
from config.settings import settings
from schemas.sessions import ConversationSession, ConversationState

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Gestionnaire de sessions conversationnelles stockées dans Redis.
    Chaque session est identifiée par le numéro de téléphone WhatsApp.
    """

    def __init__(self):
        """Initialise la connexion Redis."""
        try:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
            self.ttl = settings.redis_session_ttl
            logger.info(f"✅ SessionManager connecté à Redis: {settings.redis_url}")
        except Exception as e:
            logger.warning(
                f"⚠️ Redis indisponible ({e}). Utilisation du stockage mémoire."
            )
            self.redis_client = None
            self._memory_store: dict = {}
            self.ttl = settings.redis_session_ttl

    def _session_key(self, phone_number: str) -> str:
        """Génère la clé Redis pour une session."""
        return f"whatsapp:session:{phone_number}"

    def get_session(self, phone_number: str) -> ConversationSession:
        """
        Récupère la session d'un utilisateur, ou en crée une nouvelle.
        
        Args:
            phone_number: Numéro WhatsApp de l'utilisateur
            
        Returns:
            ConversationSession existante ou nouvelle
        """
        key = self._session_key(phone_number)

        try:
            if self.redis_client:
                data = self.redis_client.get(key)
                if data:
                    session_data = json.loads(data)
                    logger.debug(f"📂 Session trouvée pour {phone_number}")
                    return ConversationSession.from_redis_dict(session_data)
            else:
                # Fallback mémoire
                if key in self._memory_store:
                    return ConversationSession.from_redis_dict(self._memory_store[key])

        except Exception as e:
            logger.warning(f"⚠️ Erreur lecture session {phone_number}: {e}")

        # Créer une nouvelle session
        logger.info(f"🆕 Nouvelle session créée pour {phone_number}")
        return ConversationSession(
            phone_number=phone_number,
            state=ConversationState.GREETING,
        )

    def save_session(self, session: ConversationSession) -> None:
        """
        Sauvegarde la session dans Redis.
        
        Args:
            session: Session à sauvegarder
        """
        key = self._session_key(session.phone_number)
        data = json.dumps(session.to_redis_dict(), default=str)

        try:
            if self.redis_client:
                self.redis_client.setex(key, self.ttl, data)
            else:
                self._memory_store[key] = session.to_redis_dict()

            logger.debug(f"💾 Session sauvegardée pour {session.phone_number}")

        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde session: {e}")

    def delete_session(self, phone_number: str) -> None:
        """Supprime la session d'un utilisateur."""
        key = self._session_key(phone_number)

        try:
            if self.redis_client:
                self.redis_client.delete(key)
            else:
                self._memory_store.pop(key, None)

            logger.info(f"🗑️ Session supprimée pour {phone_number}")

        except Exception as e:
            logger.error(f"❌ Erreur suppression session: {e}")

    def add_message_to_history(
        self,
        phone_number: str,
        role: str,
        content: str,
    ) -> ConversationSession:
        """
        Ajoute un message à l'historique de la session.
        
        Args:
            phone_number: Numéro WhatsApp
            role: 'user' ou 'assistant'
            content: Contenu du message
            
        Returns:
            Session mise à jour
        """
        session = self.get_session(phone_number)
        session.add_message(
            role=role,
            content=content,
            max_history=settings.max_conversation_history,
        )
        self.save_session(session)
        return session

    def is_redis_available(self) -> bool:
        """Vérifie si Redis est disponible."""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False
