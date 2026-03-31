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
from tools.whatsapp_sender import send_whatsapp_message, send_whatsapp_interactive_list, send_whatsapp_buttons
from tools.catalog_service import (
    get_catalog_context, get_available_products_summary,
    get_brands_for_interactive, get_products_by_brand_for_interactive,
    get_product_details_by_code,
)
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
                interactive_type=msg_data.get("interactive_type", ""),
                interactive_id=msg_data.get("interactive_id", ""),
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


async def _handle_interactive_reply(
    phone_number: str,
    session,
    interactive_type: str,
    interactive_id: str,
    display_text: str,
) -> None:
    """
    Gère les réponses interactives : sélection de marque ou de produit.
    """
    logger.info(f"🔘 Interactive {interactive_type}: id={interactive_id} texte={display_text}")

    try:
        # ── Sélection d'une marque ──
        if interactive_id.startswith("brand_"):
            brand_name = interactive_id.replace("brand_", "")
            sections = get_products_by_brand_for_interactive(brand_name)

            if sections:
                await send_whatsapp_interactive_list(
                    to=phone_number,
                    header=f"{brand_name}",
                    body=f"Voici les produits {brand_name} disponibles 👇\nChoisis un produit pour l'ajouter à ta commande.",
                    button_text="Voir les produits",
                    sections=sections,
                    footer="Prix en DH par unité de vente",
                )
                response_text = f"Produits {brand_name} affichés"
            else:
                response_text = f"Aucun produit disponible pour {brand_name} actuellement."
                await send_whatsapp_message(to=phone_number, message=response_text)

            session.add_message("assistant", response_text, settings.max_conversation_history)
            session_manager.save_session(session)
            return

        # ── Sélection d'un produit avec quantité (add_{code}_{qty}) ──
        if interactive_id.startswith("add_"):
            parts = interactive_id.split("_", 1)[1]  # code_qty
            # Le code peut contenir des _, la quantité est le dernier segment
            last_underscore = parts.rfind("_")
            product_code = parts[:last_underscore]
            quantity = int(parts[last_underscore + 1:])
            product = get_product_details_by_code(product_code)

            if product:
                code = product["code"]
                if code in session.cart:
                    session.cart[code]["quantity"] += quantity
                else:
                    session.cart[code] = {
                        "nom": product["nom"],
                        "prix": product["prix_unite"],
                        "unite": product["unite_vente"],
                        "quantity": quantity,
                    }
                qty = session.cart[code]["quantity"]
                total_cart = sum(i["prix"] * i["quantity"] for i in session.cart.values())
                response_text = (
                    f"✅ {quantity}x {product['nom']} ajouté !\n"
                    f"Total article : {qty}x — {product['prix_unite'] * qty:.2f} DH\n"
                    f"🛒 Total panier : {total_cart:.2f} DH"
                )
                await send_whatsapp_buttons(
                    to=phone_number,
                    body=response_text,
                    buttons=[
                        {"id": "show_catalog", "title": "📦 Catalogue"},
                        {"id": "show_cart", "title": "🛒 Mon panier"},
                    ],
                )
            else:
                response_text = "Ce produit n'est plus disponible."
                await send_whatsapp_message(to=phone_number, message=response_text)

            session.add_message("assistant", response_text, settings.max_conversation_history)
            session_manager.save_session(session)
            return

        # ── Sélection d'un produit sans quantité (marques à >5 produits) ──
        if interactive_id.startswith("product_"):
            product_code = interactive_id.replace("product_", "")
            product = get_product_details_by_code(product_code)

            if product:
                code = product["code"]
                # Ajouter 1 unité par défaut + boutons quantité
                if code in session.cart:
                    session.cart[code]["quantity"] += 1
                else:
                    session.cart[code] = {
                        "nom": product["nom"],
                        "prix": product["prix_unite"],
                        "unite": product["unite_vente"],
                        "quantity": 1,
                    }
                qty = session.cart[code]["quantity"]
                total_cart = sum(i["prix"] * i["quantity"] for i in session.cart.values())
                response_text = (
                    f"✅ {product['nom']} ajouté !\n"
                    f"Quantité : {qty} | {product['prix_unite'] * qty:.2f} DH\n"
                    f"🛒 Total panier : {total_cart:.2f} DH"
                )
                await send_whatsapp_buttons(
                    to=phone_number,
                    body=response_text,
                    buttons=[
                        {"id": f"cart_plus_{code}", "title": "➕ Ajouter 1"},
                        {"id": f"cart_minus_{code}", "title": "➖ Retirer 1"},
                        {"id": "show_catalog", "title": "📦 Catalogue"},
                    ],
                )
            else:
                response_text = "Ce produit n'est plus disponible."
                await send_whatsapp_message(to=phone_number, message=response_text)

            session.add_message("assistant", response_text, settings.max_conversation_history)
            session_manager.save_session(session)
            return

        # ── Bouton "Voir le catalogue" ──
        if interactive_id == "show_catalog":
            brands_rows = get_brands_for_interactive()
            if brands_rows:
                sections = [{"title": "Marques disponibles", "rows": brands_rows}]
                await send_whatsapp_interactive_list(
                    to=phone_number,
                    body="Choisis une marque pour voir les produits disponibles 👇",
                    button_text="Nos marques 🏷️",
                    sections=sections,
                    footer="Produits en stock uniquement",
                )
            return

        # ── Bouton "Voir mon panier" ──
        if interactive_id == "show_cart":
            await _send_cart_detail(phone_number, session)
            return

        # ── Confirmer la commande ──
        if interactive_id == "confirm_order":
            if session.cart:
                lines = ["✅ *Commande confirmée !*\n"]
                total = 0.0
                for code, item in session.cart.items():
                    subtotal = item["prix"] * item["quantity"]
                    total += subtotal
                    lines.append(f"• {item['quantity']}x {item['nom']} — {subtotal:.2f} DH")
                lines.append(f"\n💰 *Total : {total:.2f} DH*")
                lines.append("\nMerci pour ta commande ! 🎉")
                lines.append("Ta commande va être traitée dans les plus brefs délais 🚚")
                lines.append("Si tu as besoin d'aide, n'hésite pas !")
                resp = "\n".join(lines)
                await send_whatsapp_message(to=phone_number, message=resp)
                session.cart = {}  # Vider le panier
                session.add_message("assistant", resp, settings.max_conversation_history)
                session_manager.save_session(session)
            return

        # ── Annuler la commande ──
        if interactive_id == "cancel_order":
            session.cart = {}
            resp = "🗑️ Commande annulée. Ton panier est vide.\nTape *catalogue* ou dis *salut* pour recommencer !"
            await send_whatsapp_message(to=phone_number, message=resp)
            session.add_message("assistant", resp, settings.max_conversation_history)
            session_manager.save_session(session)
            return

        # ── Modifier la commande (afficher les articles pour modification) ──
        if interactive_id == "modify_order":
            if session.cart:
                rows = []
                for code, item in session.cart.items():
                    subtotal = item["prix"] * item["quantity"]
                    rows.append({
                        "id": f"cart_edit_{code}",
                        "title": item["nom"][:24],
                        "description": f"{item['quantity']}x — {subtotal:.2f} DH"[:72],
                    })
                sections = [{"title": "Modifier un article", "rows": rows}]
                await send_whatsapp_interactive_list(
                    to=phone_number,
                    body="Choisis l'article à modifier 👇",
                    button_text="Mes articles",
                    sections=sections,
                )
            return

        # ── Boutons modification panier : +1 / -1 / supprimer ──
        if interactive_id.startswith("cart_plus_"):
            code = interactive_id.replace("cart_plus_", "")
            if code in session.cart:
                session.cart[code]["quantity"] += 1
                item = session.cart[code]
                total_cart = sum(i["prix"] * i["quantity"] for i in session.cart.values())
                resp = (
                    f"➕ {item['nom']}\n"
                    f"Quantité : {item['quantity']} | {item['prix'] * item['quantity']:.2f} DH\n"
                    f"🛒 Total panier : {total_cart:.2f} DH"
                )
                await send_whatsapp_buttons(
                    to=phone_number,
                    body=resp,
                    buttons=[
                        {"id": f"cart_plus_{code}", "title": "➕ Ajouter 1"},
                        {"id": f"cart_minus_{code}", "title": "➖ Retirer 1"},
                        {"id": "show_catalog", "title": "📦 Catalogue"},
                    ],
                )
                session.add_message("assistant", resp, settings.max_conversation_history)
                session_manager.save_session(session)
            return

        if interactive_id.startswith("cart_minus_"):
            code = interactive_id.replace("cart_minus_", "")
            if code in session.cart:
                session.cart[code]["quantity"] -= 1
                if session.cart[code]["quantity"] <= 0:
                    removed = session.cart.pop(code)
                    total_cart = sum(i["prix"] * i["quantity"] for i in session.cart.values())
                    resp = f"🗑️ {removed['nom']} supprimé du panier\n🛒 Total : {total_cart:.2f} DH"
                    await send_whatsapp_buttons(
                        to=phone_number,
                        body=resp,
                        buttons=[
                            {"id": "show_catalog", "title": "📦 Catalogue"},
                            {"id": "show_cart", "title": "🛒 Mon panier"},
                        ],
                    )
                else:
                    item = session.cart[code]
                    total_cart = sum(i["prix"] * i["quantity"] for i in session.cart.values())
                    resp = (
                        f"➖ {item['nom']}\n"
                        f"Quantité : {item['quantity']} | {item['prix'] * item['quantity']:.2f} DH\n"
                        f"🛒 Total panier : {total_cart:.2f} DH"
                    )
                    await send_whatsapp_buttons(
                        to=phone_number,
                        body=resp,
                        buttons=[
                            {"id": f"cart_plus_{code}", "title": "➕ Ajouter 1"},
                            {"id": f"cart_minus_{code}", "title": "➖ Retirer 1"},
                            {"id": "show_catalog", "title": "📦 Catalogue"},
                        ],
                    )
                session.add_message("assistant", resp, settings.max_conversation_history)
                session_manager.save_session(session)
            return

        if interactive_id.startswith("cart_del_"):
            code = interactive_id.replace("cart_del_", "")
            if code in session.cart:
                removed = session.cart.pop(code)
                total_cart = sum(i["prix"] * i["quantity"] for i in session.cart.values())
                resp = f"🗑️ {removed['nom']} supprimé du panier\n🛒 Total : {total_cart:.2f} DH"
                await send_whatsapp_message(to=phone_number, message=resp)
                session.add_message("assistant", resp, settings.max_conversation_history)
                session_manager.save_session(session)
            return

        # ── Sélection d'un article du panier pour modification ──
        if interactive_id.startswith("cart_edit_"):
            code = interactive_id.replace("cart_edit_", "")
            if code in session.cart:
                await _send_cart_action_buttons(phone_number, code, session.cart[code])
            return

    except Exception as e:
        logger.error(f"❌ Erreur traitement interactif: {e}", exc_info=True)
        await send_whatsapp_message(
            to=phone_number,
            message="😔 Désolé, un problème est survenu. Réessaie dans quelques instants."
        )


async def _send_cart_detail(phone_number: str, session) -> None:
    """Affiche le panier en UN SEUL message bouton avec recap + 3 actions."""
    if not session.cart:
        await send_whatsapp_message(to=phone_number, message="🛒 Ton panier est vide.\nTape *catalogue* pour voir nos produits !")
        return

    lines = ["🛒 *Ton panier :*\n"]
    total = 0.0
    for code, item in session.cart.items():
        subtotal = item["prix"] * item["quantity"]
        total += subtotal
        lines.append(f"• {item['quantity']}x {item['nom']} — {subtotal:.2f} DH")
    lines.append(f"\n💰 *Total : {total:.2f} DH*")
    body_text = "\n".join(lines)

    await send_whatsapp_buttons(
        to=phone_number,
        body=body_text,
        buttons=[
            {"id": "confirm_order", "title": "✅ Confirmer"},
            {"id": "modify_order", "title": "✏️ Modifier"},
            {"id": "cancel_order", "title": "❌ Annuler"},
        ],
    )

    session.add_message("assistant", body_text, settings.max_conversation_history)
    session_manager.save_session(session)


async def _send_cart_action_buttons(phone_number: str, code: str, item: dict) -> None:
    """Envoie les boutons +1 / -1 / Supprimer pour un article du panier."""
    await send_whatsapp_buttons(
        to=phone_number,
        body=f"{item['nom']}\nQuantité : {item['quantity']}",
        buttons=[
            {"id": f"cart_plus_{code}", "title": "➕ Ajouter 1"},
            {"id": f"cart_minus_{code}", "title": "➖ Retirer 1"},
            {"id": f"cart_del_{code}", "title": "🗑️ Supprimer"},
        ],
    )

async def _send_catalog_buttons(phone_number: str) -> None:
    """Envoie les boutons 'Voir le catalogue' et 'Mon panier' après un ajout."""
    await send_whatsapp_buttons(
        to=phone_number,
        body="Que veux-tu faire ?",
        buttons=[
            {"id": "show_catalog", "title": "📦 Catalogue"},
            {"id": "show_cart", "title": "🛒 Mon panier"},
        ],
    )


def _format_cart_for_prompt(cart: dict) -> str:
    """Formate le panier pour injection dans le system prompt Mistral."""
    if not cart:
        return "Panier vide."
    lines = []
    total = 0.0
    for code, item in cart.items():
        subtotal = item["prix"] * item["quantity"]
        total += subtotal
        lines.append(f"- {item['quantity']}x {item['nom']} — {subtotal:.2f} DH")
    lines.append(f"Total : {total:.2f} DH")
    return "\n".join(lines)


async def process_incoming_message(
    phone_number: str,
    message_text: str,
    profile_name: str = "",
    message_type: str = "text",
    media_id: str = "",
    interactive_type: str = "",
    interactive_id: str = "",
) -> None:
    """
    Traite un message WhatsApp entrant avec Mistral IA directement.
    Supporte les messages texte, vocaux et interactifs (listes, boutons).
    """
    logger.info(f"📨 Traitement message ({message_type}/{interactive_type or 'N/A'}) de {phone_number} ({profile_name})")
    
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
        
        # ── 2b. Traiter les réponses interactives (sélection liste / bouton) ──
        if message_type == "interactive" and interactive_id:
            await _handle_interactive_reply(
                phone_number, session, interactive_type, interactive_id, message_text
            )
            return
        
        # ── 2c. Produit en attente de quantité ──
        if session.pending_product and message_text.strip().isdigit():
            quantity = int(message_text.strip())
            product = get_product_details_by_code(session.pending_product)
            session.pending_product = None  # Réinitialiser

            if product and quantity > 0:
                # Ajouter au panier
                code = product["code"]
                if code in session.cart:
                    session.cart[code]["quantity"] += quantity
                else:
                    session.cart[code] = {
                        "nom": product["nom"],
                        "prix": product["prix_unite"],
                        "unite": product["unite_vente"],
                        "quantity": quantity,
                    }

                total_item = product["prix_unite"] * quantity
                total_cart = sum(
                    item["prix"] * item["quantity"]
                    for item in session.cart.values()
                )

                response_text = (
                    f"✅ Ajouté : {quantity}x {product['nom']} — {total_item:.2f} DH\n"
                    f"🛒 Total panier : {total_cart:.2f} DH"
                )
                await send_whatsapp_message(to=phone_number, message=response_text)
                await _send_catalog_buttons(phone_number)
            else:
                response_text = "Quantité invalide ou produit indisponible. Réessaie."
                await send_whatsapp_message(to=phone_number, message=response_text)

            session.add_message("assistant", response_text, settings.max_conversation_history)
            session_manager.save_session(session)
            return
        
        # ── 2d. Détection d'intention : catalogue / panier / commande ──
        msg_lower = message_text.lower().strip()
        
        # Mots-clés catalogue (même en phrase complète)
        catalog_triggers = ["catalogue", "catalog", "produits", "marques", "menu",
                            "voir les produits", "voir les marques", "vos produits",
                            "vos marques", "qu'est-ce que vous avez", "qu'avez-vous",
                            "chnou 3ndkom", "chnou kayn", "ach kayn", "les produits"]
        if any(trigger in msg_lower for trigger in catalog_triggers):
            brands_rows = get_brands_for_interactive()
            if brands_rows:
                sections = [{"title": "Marques disponibles", "rows": brands_rows}]
                await send_whatsapp_interactive_list(
                    to=phone_number,
                    body="Voici nos marques disponibles 👇\nChoisis-en une pour voir les produits en stock.",
                    button_text="Nos marques 🏷️",
                    sections=sections,
                    footer="Produits en stock uniquement",
                )
            session.add_message("assistant", "Catalogue affiché", settings.max_conversation_history)
            session_manager.save_session(session)
            return
        
        # Mots-clés panier
        panier_triggers = ["panier", "cart", "mon panier", "le panier", "voir ma commande",
                           "récap", "recapitulatif", "ma commande", "l panier", "le panier dyali"]
        if any(trigger in msg_lower for trigger in panier_triggers):
            await _send_cart_detail(phone_number, session)
            return
        
        # Mots-clés confirmer commande
        confirm_triggers = ["confirmer", "valider", "c'est bon", "c'est tout", "safi",
                            "khalas", "aked", "confirme"]
        if any(trigger in msg_lower for trigger in confirm_triggers) and session.cart:
            await _send_cart_detail(phone_number, session)
            return
        
        # 3. Détecter les salutations
        salutations = ["salut", "bonjour", "coucou", "hello", "hi", "hey", "ça va", "comment allez", "salam", "slm"]
        msg_words = msg_lower.replace(",", " ").replace("!", " ").replace("?", " ").split()
        is_greeting = any(greeting in msg_words for greeting in salutations) or msg_lower in salutations
        
        if is_greeting:
            # Réponse de bienvenue + liste interactive des marques
            client_display = session.client_name or ""
            
            # Détecter si salutation en darija/arabe ou français
            darija_greetings = ["salam", "slm"]
            is_darija = any(g in msg_words for g in darija_greetings)
            
            if is_darija:
                welcome_body = (
                    f"Merhba {client_display}! 👋\n\n"
                    "Ana l'assistant Oulmès, n9der n3awnk tchouf les produits "
                    "o tcommandi directement mn hna.\n\n"
                    "Chouf les marques dyalna 👇"
                )
                button_text = "Nos marques 🏷️"
            else:
                welcome_body = (
                    f"Bienvenue {client_display} ! 👋\n\n"
                    "Je suis l'assistant Oulmès, je peux t'aider à consulter "
                    "nos produits et passer ta commande.\n\n"
                    "Découvre nos marques 👇"
                )
                button_text = "Nos marques 🏷️"
            
            brands_rows = get_brands_for_interactive()
            if brands_rows:
                sections = [{"title": "Marques disponibles", "rows": brands_rows}]
                await send_whatsapp_interactive_list(
                    to=phone_number,
                    body=welcome_body,
                    button_text=button_text,
                    sections=sections,
                    footer="Choisis une marque pour voir les produits",
                )
                response_text = welcome_body
            else:
                response_text = welcome_body + "\n\n⚠️ Catalogue indisponible."
                await send_whatsapp_message(to=phone_number, message=response_text)
            
            # Sauvegarder dans l'historique
            session.add_message("assistant", response_text, settings.max_conversation_history)
            session_manager.save_session(session)
            logger.info(f"✅ Message de bienvenue interactif envoyé à {phone_number}")
            return
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

# PANIER ACTUEL DU CLIENT
{_format_cart_for_prompt(session.cart)}

# IMPORTANT — Données produits
- Utilise UNIQUEMENT les produits et prix listés ci-dessus
- Ne jamais inventer de produits ou de prix
- Si un produit n'est pas dans le catalogue, indique qu'il n'est pas disponible
- Les prix sont en DH par unité de vente (caisse ou pack)
- Le client peut parcourir le catalogue interactif en tapant "catalogue"
- S'il demande un produit qui n'existe pas, suggère-lui de taper "catalogue" pour voir les produits disponibles

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
