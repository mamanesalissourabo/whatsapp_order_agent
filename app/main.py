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
from crew.crew_manager import get_crew_manager
from tools import SearchProductsTool, AddToCartTool, RemoveFromCartTool, ViewCartTool

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
    
    # Initialiser la Crew avec les outils
    tools = [
        SearchProductsTool(),
        AddToCartTool(),
        RemoveFromCartTool(),
        ViewCartTool(),
    ]
    get_crew_manager(tools=tools)
    logger.info("🤖 CrewManager initialisé avec les outils")
    
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
) -> None:
    """
    Traite un message WhatsApp entrant en arrière-plan.
    
    1. Récupère/crée la session
    2. Ajoute le message à l'historique
    3. Lance la Crew d'agents pour générer la réponse
    4. Envoie la réponse via WhatsApp
    5. Sauvegarde la session mise à jour
    """
    logger.info(f"📨 Traitement message de {phone_number} ({profile_name}): {message_text[:80]}")
    
    try:
        # 1. Récupérer la session
        session = session_manager.get_session(phone_number)
        
        # Mettre à jour le nom du client si disponible
        if profile_name and not session.client_name:
            session.client_name = profile_name
        
        # 2. Ajouter le message utilisateur à l'historique
        session.add_message("user", message_text, settings.max_conversation_history)
        session_manager.save_session(session)
        
        # 3. Préparer le contexte et lancer la Crew
        context = session.get_context()
        crew_manager = get_crew_manager()
        
        result = crew_manager.process_message(
            message=message_text,
            phone_number=phone_number,
            context=context,
        )
        
        response_text = result.get("message", "")
        
        if not response_text:
            response_text = (
                "😔 Désolé, je n'ai pas pu traiter votre demande. "
                "Pouvez-vous reformuler?"
            )
        
        # 4. Envoyer la réponse via WhatsApp
        await send_whatsapp_message(to=phone_number, message=response_text)
        
        # 5. Sauvegarder la réponse dans l'historique
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
