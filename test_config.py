"""Script pour tester la configuration de l'application."""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from config.settings import settings
    
    print("✅ Configuration chargée avec succès!\n")
    print("📋 Configuration actuelle:")
    print(f"  - App Name: {settings.app_name}")
    print(f"  - Version: {settings.app_version}")
    print(f"  - Debug: {settings.debug}")
    print(f"  - Host: {settings.app_host}:{settings.app_port}")
    print(f"  - Log Level: {settings.log_level}")
    print(f"\n🤖 Mistral AI:")
    print(f"  - Model: {settings.mistral_model}")
    print(f"  - API Key: {'✓ Configurée' if settings.mistral_api_key else '✗ Manquante'}")
    print(f"\n📱 WhatsApp:")
    print(f"  - Phone Number ID: {settings.whatsapp_phone_number_id}")
    print(f"  - Access Token: {'✓ Configuré' if settings.whatsapp_access_token else '✗ Manquant'}")
    print(f"  - Verify Token: {'✓ Configuré' if settings.whatsapp_verify_token else '✗ Manquant'}")
    print(f"\n💾 Base de données:")
    print(f"  - Selfcare DB: {settings.selfcare_db_url.split('@')[-1] if '@' in settings.selfcare_db_url else settings.selfcare_db_url}")
    print(f"\n📦 Redis:")
    print(f"  - URL: {settings.redis_url}")
    print(f"  - Session TTL: {settings.redis_session_ttl}s")
    
except Exception as e:
    print(f"❌ Erreur de configuration: {e}")
    print("\n💡 Assurez-vous d'avoir:")
    print("  1. Créé le fichier .env à partir de .env.example")
    print("  2. Installé les dépendances: pip install -r requirements.txt")
