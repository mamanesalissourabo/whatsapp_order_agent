"""
Module de transcription audio pour les messages vocaux WhatsApp.
Télécharge l'audio depuis l'API Meta, puis transcrit via Groq Whisper.
"""

import httpx
import logging
import tempfile
import os
from config.settings import settings

logger = logging.getLogger(__name__)


async def download_whatsapp_audio(media_id: str) -> bytes:
    """
    Télécharge un fichier audio depuis l'API WhatsApp Media.
    
    1. Récupère l'URL du media via l'API Meta
    2. Télécharge le fichier audio
    """
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    
    async with httpx.AsyncClient() as client:
        # Étape 1 : obtenir l'URL du media
        media_url_response = await client.get(
            f"{settings.whatsapp_api_url}/{media_id}",
            headers=headers,
        )
        media_url_response.raise_for_status()
        media_url = media_url_response.json().get("url")
        
        if not media_url:
            raise ValueError(f"URL du media introuvable pour media_id={media_id}")
        
        # Étape 2 : télécharger le fichier audio
        audio_response = await client.get(media_url, headers=headers)
        audio_response.raise_for_status()
        
        logger.info(f"🎵 Audio téléchargé: {len(audio_response.content)} octets")
        return audio_response.content


async def transcribe_audio(audio_bytes: bytes) -> str:
    """
    Transcrit un fichier audio en texte via Groq Whisper API.
    Supporte français, darija marocaine, arabe.
    """
    from groq import Groq
    
    api_key = settings.groq_api_key
    if not api_key:
        # Fallback : lire directement depuis l'environnement
        api_key = os.environ.get("GROQ_API_KEY", "")
    
    if not api_key:
        raise ValueError("GROQ_API_KEY non configurée")
    
    groq_client = Groq(api_key=api_key)
    
    # Sauvegarder temporairement le fichier audio
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    
    try:
        with open(tmp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                file=("audio.ogg", audio_file.read()),
                model="whisper-large-v3",
                temperature=0,
                response_format="verbose_json",
            )
        
        text = transcription.text.strip() if hasattr(transcription, 'text') else str(transcription).strip()
        logger.info(f"🎤 Transcription: {text[:100]}...")
        return text
        
    finally:
        os.unlink(tmp_path)


async def process_voice_message(media_id: str) -> str:
    """
    Pipeline complet : télécharge l'audio WhatsApp puis transcrit en texte.
    """
    try:
        audio_bytes = await download_whatsapp_audio(media_id)
        text = await transcribe_audio(audio_bytes)
        
        if not text:
            return ""
        
        return text
        
    except Exception as e:
        logger.error(f"❌ Erreur transcription vocale: {e}", exc_info=True)
        return ""
