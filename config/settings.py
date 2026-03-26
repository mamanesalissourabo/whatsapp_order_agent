"""
Configuration de l'application WhatsApp Order Agent.
Utilise Pydantic Settings pour charger les variables d'environnement.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Configuration de l'application."""
    
    # Configuration Mistral AI
    mistral_api_key: str
    mistral_model: str = "mistral-small-latest"
    
    # Configuration WhatsApp Business API
    whatsapp_access_token: str
    whatsapp_verify_token: str
    whatsapp_phone_number_id: str
    whatsapp_api_url: str = "https://graph.facebook.com/v18.0"
    
    # Configuration base de données Selfcare
    selfcare_db_url: str
    
    # Configuration Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_session_ttl: int = 1800  # 30 minutes en secondes
    
    # Configuration application
    app_host: str = "0.0.0.0"
    app_port: int = 8001
    debug: bool = False
    app_name: str = "WhatsApp Order Agent"
    app_version: str = "1.0.0"
    
    # Configuration logging
    log_level: str = "INFO"
    
    # Configuration sessions
    max_conversation_history: int = 5  # Nombre de messages à garder en historique
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Instance globale des settings
settings = Settings()
