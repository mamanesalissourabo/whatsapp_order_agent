"""
Application FastAPI principale pour WhatsApp Order Agent.
Point d'entrée de l'API REST et des webhooks WhatsApp.
"""

from fastapi import FastAPI, Request, Response, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from config.settings import settings
from schemas.messages import WhatsAppWebhookPayload
from tools.session_manager import SessionManager
from tools.whatsapp_sender import send_whatsapp_message
from tools.catalog_service import get_catalog_context, get_available_products_summary
from tools.audio_transcriber import process_voice_message
from database.catalog_db import init_catalog_db, seed_catalog
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage

# Configuration du logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Instances globales
session_manager: SessionManager = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    global session_manager
    
    # Startup
    logger.info("🚀 Démarrage de WhatsApp Order Agent")
    logger.info(f"📱 WhatsApp Phone Number ID: {settings.whatsapp_phone_number_id}")
    logger.info(f"🤖 Modèle Mistral: {settings.mistral_model}")
    logger.info(f"💾 Base de données Selfcare: {settings.selfcare_db_url.split('@')[-1]}")
    
    # Initialiser le gestionnaire de sessions
    session_manager = SessionManager()
    redis_status = "✅ connecté" if session_manager.is_redis_available() else "⚠️ fallback mémoire"
    logger.info(f"🔑 Redis: {redis_status}")
    
    # Initialiser et peupler le catalogue produits
    init_catalog_db()
    seed_catalog()
    logger.info("📦 Catalogue produits initialisé")
    
    yield
    
    # Shutdown
    logger.info("👋 Arrêt de WhatsApp Order Agent")


# Création de l'application FastAPI
app = FastAPI(
    title=settings.app_name,
    description="Agent IA multi-agents pour prise de commandes B2B via WhatsApp",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Endpoint racine - Informations sur l'API."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "description": "Agent IA multi-agents pour prise de commandes B2B via WhatsApp",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "webhook": "/webhooks/whatsapp"
        }
    }


@app.get("/health")
async def health_check():
    """Endpoint de health check."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version
    }


@app.get("/webhooks/whatsapp")
async def verify_webhook(request: Request):
    """
    Vérification du webhook WhatsApp par Meta.
    Appelé lors de la configuration du webhook dans Meta Developer Console.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    logger.info(f"🔍 Vérification webhook: mode={mode}, token={'✓' if token else '✗'}")
    
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        logger.info("✅ Webhook vérifié avec succès")
        return Response(content=challenge, media_type="text/plain")
    else:
        logger.warning("❌ Échec de vérification du webhook")
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Webhook pour recevoir les messages WhatsApp.
    Endpoint appelé par Meta lorsqu'un message est reçu.
    """
    try:
        body = await request.json()
        logger.info(f"📨 Webhook reçu")
        
        # 1. Extraire les messages du payload
        payload = WhatsAppWebhookPayload(**body)
        messages = payload.extract_messages()
        
        if not messages:
            logger.debug("Pas de message texte dans ce webhook (statut, read receipt, etc.)")
            return JSONResponse(status_code=200, content={"status": "no_message"})
        
        # 2. Traiter chaque message en arrière-plan
        for msg_data in messages:
            background_tasks.add_task(
                process_incoming_message,
                phone_number=msg_data["phone_number"],
                message_text=msg_data["message_text"],
                profile_name=msg_data["profile_name"],
                message_type=msg_data.get("message_type", "text"),
                media_id=msg_data.get("media_id", ""),
            )
        
        # Toujours retourner 200 immédiatement à Meta
        return JSONResponse(status_code=200, content={"status": "received"})
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du traitement du webhook: {str(e)}")
        # Toujours retourner 200 à Meta pour éviter les retries
        return JSONResponse(
            status_code=200,
            content={"status": "error", "message": str(e)}
        )


async def process_incoming_message(
    phone_number: str,
    message_text: str,
    profile_name: str = "",
    message_type: str = "text",
    media_id: str = "",
) -> None:
    """
    Traite un message WhatsApp entrant avec Mistral IA directement.
    Supporte les messages texte et vocaux.
    """
    logger.info(f"📨 Traitement message ({message_type}) de {phone_number} ({profile_name})")
    
    try:
        # 0. Si message vocal, transcrire d'abord
        if message_type == "audio" and media_id:
            logger.info(f"🎤 Transcription vocale en cours pour {phone_number}...")
            message_text = await process_voice_message(media_id)
            
            if not message_text:
                await send_whatsapp_message(
                    to=phone_number,
                    message="Désolé, je n'ai pas pu comprendre ton message vocal 🎤\nEssaie de renvoyer ou écris-moi en texte."
                )
                return
            
            logger.info(f"🎤 Transcription: {message_text[:80]}")
        
        # 1. Récupérer la session
        session = session_manager.get_session(phone_number)
        
        # Mettre à jour le nom du client si disponible
        if profile_name and not session.client_name:
            session.client_name = profile_name
        
        # 2. Ajouter le message utilisateur à l'historique
        session.add_message("user", message_text, settings.max_conversation_history)
        session_manager.save_session(session)
        
        # 3. Détecter les salutations
        salutations = ["salut", "bonjour", "coucou", "hello", "hi", "hey", "ça va", "comment allez", "salam", "slm"]
        msg_lower = message_text.lower().strip()
        msg_words = msg_lower.replace(",", " ").replace("!", " ").replace("?", " ").split()
        is_greeting = any(greeting in msg_words for greeting in salutations) or msg_lower in salutations
        
        if is_greeting:
            # Réponse de bienvenue avec marques disponibles
            brands_summary = get_available_products_summary()
            client_display = session.client_name or ""
            
            # Détecter si salutation en darija/arabe ou français
            darija_greetings = ["salam", "slm"]
            is_darija = any(g in msg_words for g in darija_greetings)
            
            if is_darija:
                response_text = f"""Merhba {client_display}! 👋

Ana l'assistant Oulmès, n9der n3awnk tchouf les produits o tcommandi directement mn hna.

🏷️ Nos marques :
{brands_summary}

Chnou bghiti tchouf ? 😊"""
            else:
                response_text = f"""Bienvenue {client_display} ! 👋

Je suis l'assistant Oulmès, je peux t'aider à consulter nos produits et passer ta commande directement ici.

🏷️ Nos marques :
{brands_summary}

Qu'est-ce qui t'intéresse ? 😊"""
        else:
            # 4. Générer une réponse avec Mistral IA
            client = MistralClient(api_key=settings.mistral_api_key)
            
            client_name = session.client_name or "client"
            catalog = get_catalog_context()
            
            system_prompt = f"""# Rôle
Tu es l'assistant IA de prise de commandes pour **Les Eaux Minérales d'Oulmès**.
Tu communiques par WhatsApp avec des **points de vente** (épiceries, cafés, restaurants, supérettes) au Maroc.

# Identité du client
- Nom : {client_name}
- Téléphone : {phone_number}

{catalog}

# IMPORTANT — Données produits
- Utilise UNIQUEMENT les produits et prix listés ci-dessus
- Ne jamais inventer de produits ou de prix
- Si un produit n'est pas dans le catalogue, indique qu'il n'est pas disponible
- Les prix sont en DH par unité de vente (caisse ou pack)

# Tes capacités
1. **Catalogue** : présenter les produits avec les prix RÉELS du catalogue
2. **Commande** : aider le point de vente à constituer sa commande (produits, quantités)
3. **Panier** : ajouter, modifier, supprimer des articles, afficher le récapitulatif avec total
4. **Suivi** : donner le statut d'une commande existante
5. **Questions** : répondre aux questions sur les produits, délais de livraison, promotions

# Règles STRICTES
- **Langue** : détecte la langue du client et réponds TOUJOURS dans la même langue :
  - Si le client écrit en **darija marocaine** (ex: "bghit", "3afak", "chhal", "wach"), réponds **100% en darija**. Ne mélange JAMAIS avec du français. Pas de "Voici", "Commande en cours", etc.
  - Si le client écrit en **français**, réponds **100% en français**
  - Si le client écrit en **arabe classique**, réponds en **arabe**
  - Par défaut, utilise le **français**
  - **INTERDIT** de changer de langue en cours de conversation. Si le client parle darija, TOUT ton message doit être en darija.
- Sois **concis** : messages courts adaptés à WhatsApp (pas de pavés)
- Utilise des **emojis** avec modération (1-3 par message)
- **Jamais** de préambule type "Voici ma réponse", "Bien sûr", "En tant qu'assistant"
- Va **droit au but** : commence directement par l'information utile
- Quand tu listes des produits, inclus toujours le **prix** et l'**unité de vente**

# Ajout au panier
- Quand le client commande un produit, dis que la commande a été **ajoutée** (pas "en cours")
  - En darija : "Tzadet f le panier dyalk ✅" ou "T7attet f la commande ✅"
  - En français : "Ajouté à ta commande ✅"
- **TOUJOURS afficher le total** après chaque ajout (ex: "Total : 126.00 DH" ou "Lmajmou3 : 126.00 DH")
- Après l'ajout, demande s'il veut ajouter autre chose (dans la langue du client)
  - En darija : "Bghiti tzid chi 7aja khra ?"
  - En français : "Tu veux ajouter autre chose ?"
- Ne dis JAMAIS "Kif dayr" ou d'autres phrases hors contexte
- Quand tu listes des produits pour un client qui parle **darija**, n'utilise PAS "Voici les produits". Dis plutôt "Hak les produits" ou "3ndna f Bahia :"
- Les codes produits (ex: BAH-033-MIX) sont internes, ne les affiche PAS au client
- Termine par une **question** pour guider le client vers l'étape suivante
- Ne répète pas le message du client dans ta réponse

# Ton
Professionnel mais chaleureux. Tu tutoies le client. Tu es efficace et orienté action.

# Fin de commande
Quand le client indique qu'il a fini sa commande (ex: "c'est bon", "non merci", "c'est tout", "khalas", "safi", "mzyan", "aked"), tu DOIS :
1. Récapituler la commande complète avec le total — DANS LA LANGUE DU CLIENT :
   - En darija : "La commande dyalk :" (PAS "Commande récapitulative", PAS "Récapitulatif")
   - En français : "Récapitulatif de ta commande :"
2. Afficher le total :
   - En darija : "Lmajmou3 : 210.00 DH" (PAS "Total")
   - En français : "Total : 210.00 DH"
3. Remercier : darija → "Choukran 3la la commande !" / français → "Merci pour ta commande !"
4. Rassurer : darija → "Ghadi tittraita f a9rab wa9t 🚚" / français → "Ta commande va être traitée dans les plus brefs délais 🚚"
5. Proposer de revenir : darija → "Ila 7tajiti chi 7aja, rje3 liya!" / français → "Si tu as besoin d'aide, n'hésite pas !"
6. Souhaiter bonne journée : darija → "Nhar sa3id! 😊" / français → "Bonne journée ! 😊"
IMPORTANT : AUCUN mot français dans un message darija. Pas de "Commande", "Récapitulatif", "Total", "Ajouté"."""
            
            messages = [ChatMessage(role="system", content=system_prompt)]
            for msg in session.history[-6:]:
                messages.append(ChatMessage(role=msg["role"], content=msg["content"]))
            
            response = client.chat(
                model=settings.mistral_model,
                messages=messages,
                temperature=0.5,
            )
            response_text = response.choices[0].message.content.strip()
            
            # Nettoyer le texte généré par Mistral
            # Enlever les phrases du type "Voici une réponse...", "Ton naturel...", etc.
            lines = response_text.split('\n')
            cleaned_lines = []
            skip_until_empty = False
            
            for line in lines:
                line_lower = line.lower()
                # Sauter les lignes d'explication
                if any(phrase in line_lower for phrase in [
                    "voici une réponse",
                    "ton naturel",
                    "proposition d'aide",
                    "voici comment",
                    "c'est important",
                    "réponse directe",
                    "explication"
                ]):
                    skip_until_empty = True
                    continue
                
                if skip_until_empty and line.strip() == "":
                    skip_until_empty = False
                    continue
                
                if not skip_until_empty:
                    cleaned_lines.append(line)
            
            response_text = '\n'.join(cleaned_lines).strip()
            
            if not response_text:
                response_text = "Comment puis-je vous aider?"
        
        # 5. Envoyer la réponse via WhatsApp
        await send_whatsapp_message(to=phone_number, message=response_text)
        
        # 6. Sauvegarder la réponse dans l'historique
        session.add_message("assistant", response_text, settings.max_conversation_history)
        session_manager.save_session(session)
        
        logger.info(f"✅ Réponse envoyée à {phone_number}")
        
    except Exception as e:
        logger.error(f"❌ Erreur traitement message de {phone_number}: {e}", exc_info=True)
        
        # Envoyer un message d'erreur à l'utilisateur
        error_msg = (
            "😔 Désolé, j'ai rencontré un problème technique. "
            "Veuillez réessayer dans quelques instants."
        )
        await send_whatsapp_message(to=phone_number, message=error_msg)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Gestionnaire global d'exceptions."""
    logger.error(f"❌ Erreur non gérée: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug
    )
