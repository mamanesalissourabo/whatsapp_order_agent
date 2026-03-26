"""
Définition des tâches (Tasks) pour les agents CrewAI.
Chaque tâche correspond à une étape du workflow de traitement des messages.
"""

from crewai import Task, Agent
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


def create_analyze_intent_task(agent, message: str, context: Dict[str, Any]) -> Task:
    """
    Tâche d'analyse d'intention pour l'agent Analyst.
    
    Args:
        agent: L'agent Analyst
        message: Le message utilisateur à analyser
        context: Contexte de la conversation (historique, état du panier, etc.)
    """
    context_str = f"""
Message utilisateur: "{message}"

Contexte de la conversation:
- Historique: {context.get('history', [])}
- Panier actuel: {context.get('cart', [])}
- Client sélectionné: {context.get('client_id', 'Non défini')}
- État: {context.get('state', 'UNKNOWN')}
"""
    
    return Task(
        description=f"""Analyse le message de l'utilisateur et détermine son intention.
        
{context_str}

Identifie:
1. L'intention principale (COMMANDER, QUESTION_PRODUIT, MODIFIER_PANIER, SUIVI_COMMANDE, AIDE, SALUTATION)
2. Les entités mentionnées (produits, quantités, numéros de commande)
3. Le niveau de confiance de ton analyse
4. Si des informations manquent pour accomplir l'intention

Retourne un JSON structuré avec:
{{
    "intention": "...",
    "entites": {{"produits": [...], "quantites": [...], ...}},
    "confiance": 0.0-1.0,
    "informations_manquantes": [...]
}}""",
        agent=agent,
        expected_output="Un JSON structuré contenant l'intention détectée et les entités extraites"
    )


def create_plan_strategy_task(agent, analysis: str, context: Dict[str, Any]) -> Task:
    """
    Tâche de planification pour l'agent Strategist.
    
    Args:
        agent: L'agent Strategist
        analysis: Résultat de l'analyse de l'agent Analyst
        context: Contexte de la conversation
    """
    return Task(
        description=f"""Basé sur l'analyse de l'intention, planifie la stratégie d'action.

Analyse reçue: {analysis}

Contexte:
- Panier actuel: {context.get('cart', [])}
- Client: {context.get('client_name', 'Non identifié')}
- Produits disponibles: {context.get('available_products_count', 'À déterminer')}

Selon l'intention détectée:

**Si COMMANDER**: 
- Identifie les produits à chercher
- Vérifie les quantités demandées
- Prépare l'ajout au panier
- Suggère des quantités standards si floues

**Si QUESTION_PRODUIT**:
- Identifie les informations produit nécessaires (prix, disponibilité, description)
- Prépare la requête de recherche

**Si MODIFIER_PANIER**:
- Détermine les modifications (ajout, suppression, changement quantité)
- Valide la cohérence

**Si SUIVI_COMMANDE**:
- Identifie le numéro de commande ou prépare liste commandes récentes

Retourne un plan d'action structuré avec les étapes à exécuter.""",
        agent=agent,
        expected_output="Un plan d'action détaillé avec les opérations à effectuer"
    )


def create_execute_action_task(agent, plan: str, context: Dict[str, Any]) -> Task:
    """
    Tâche d'exécution pour l'agent Integrator.
    
    Args:
        agent: L'agent Integrator (avec outils)
        plan: Plan d'action du Strategist
        context: Contexte de la conversation
    """
    return Task(
        description=f"""Exécute le plan d'action en utilisant les outils disponibles.

Plan à exécuter: {plan}

Contexte système:
- Numéro WhatsApp: {context.get('phone_number', 'Inconnu')}
- Client ID: {context.get('client_id', 'Non identifié')}

Utilise les outils à ta disposition:
- SearchProductsTool: pour rechercher des produits
- AddToCartTool: pour ajouter au panier
- GetClientInfoTool: pour récupérer info client
- CreateOrderTool: pour créer une commande
- GetOrderStatusTool: pour vérifier statut commande

Exécute les actions demandées et retourne les résultats de manière structurée.
En cas d'erreur, retourne un message d'erreur clair avec la cause.

Format de retour:
{{
    "success": true/false,
    "data": {{...}},
    "error": "message d'erreur si applicable",
    "actions_executees": [...]
}}""",
        agent=agent,
        expected_output="Un JSON avec les résultats de l'exécution des actions"
    )


def create_compose_response_task(agent, execution_result: str, context: Dict[str, Any]) -> Task:
    """
    Tâche de composition de réponse pour l'agent Communicator.
    
    Args:
        agent: L'agent Communicator
        execution_result: Résultat de l'exécution de l'Integrator
        context: Contexte de la conversation
    """
    return Task(
        description=f"""Compose un message WhatsApp final basé sur les résultats d'exécution.

Résultats d'exécution: {execution_result}

Contexte conversation:
- Historique: {context.get('history', [])}
- État du panier: {context.get('cart', [])}

Rédige un message qui:
1. Répond directement à la demande de l'utilisateur
2. Confirme les actions effectuées (produits ajoutés, commande créée, etc.)
3. Présente l'information de manière claire et structurée
4. Inclut les prochaines étapes si nécessaire
5. Utilise des emojis appropriés (📦 🛒 ✅ 🚚 💰 📋)

Règles de style:
- Ton professionnel mais chaleureux (B2B)
- Phrases courtes et claires
- Utilise des listes pour plusieurs items
- Maximum 3-4 phrases pour ne pas surcharger WhatsApp
- Toujours finir par une question ou action suggérée

Exemples de bon format:
- "✅ J'ai ajouté 10 caisses d'Oulmes 1.5L à votre panier\\n\\nVotre panier: 📦\\n1. Oulmes 1.5L - 10 caisses\\n\\nVoulez-vous valider la commande?"
- "📋 Voici vos produits disponibles:\\n1. Oulmes 1.5L - 45.50 MAD/caisse\\n2. Oulmes 0.5L - 28.00 MAD/caisse\\n\\nQue souhaitez-vous commander?"

Retourne uniquement le texte du message, sans JSON.""",
        agent=agent,
        expected_output="Le message WhatsApp final à envoyer à l'utilisateur"
    )


class TaskFactory:
    """Factory pour créer les tâches avec leur configuration."""
    
    @staticmethod
    def create_conversation_tasks(
        agents: Dict[str, Agent],
        message: str,
        context: Dict[str, Any]
    ) -> list:
        """
        Crée la séquence de tâches pour traiter un message.
        
        Args:
            agents: Dictionnaire des agents disponibles
            message: Message utilisateur
            context: Contexte de la conversation
            
        Returns:
            Liste de tâches dans l'ordre d'exécution
        """
        logger.info(f"📋 Création des tâches pour le message: {message[:50]}...")
        
        # Tâche 1: Analyse de l'intention
        analyze_task = create_analyze_intent_task(
            agents['analyst'],
            message,
            context
        )
        
        # Tâche 2: Planification de la stratégie
        # Note: Cette tâche recevra le résultat de analyze_task
        plan_task = create_plan_strategy_task(
            agents['strategist'],
            "{{analyze_task.output}}",  # Référence à la tâche précédente
            context
        )
        
        # Tâche 3: Exécution des actions
        execute_task = create_execute_action_task(
            agents['integrator'],
            "{{plan_task.output}}",
            context
        )
        
        # Tâche 4: Composition de la réponse
        compose_task = create_compose_response_task(
            agents['communicator'],
            "{{execute_task.output}}",
            context
        )
        
        tasks = [analyze_task, plan_task, execute_task, compose_task]
        logger.info(f"✅ {len(tasks)} tâches créées")
        
        return tasks
