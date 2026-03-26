"""
Définition des agents CrewAI pour le système de prise de commandes WhatsApp.
Chaque agent a un rôle spécifique dans le traitement des messages clients.
"""

from crewai import Agent
from langchain_mistralai import ChatMistralAI
from config.settings import settings
import logging

logger = logging.getLogger(__name__)


def create_llm():
    """Crée une instance du modèle Mistral AI."""
    return ChatMistralAI(
        model=settings.mistral_model,
        api_key=settings.mistral_api_key,
        temperature=0.7,
    )


def create_analyst_agent(llm) -> Agent:
    """
    Agent Analyst : Analyste des intentions utilisateur.
    Responsable de comprendre ce que l'utilisateur veut faire.
    """
    return Agent(
        role='Analyste des intentions',
        goal='Déterminer précisément ce que l\'utilisateur veut faire',
        backstory="""Expert en compréhension du langage naturel. 
        Tu identifies si l'utilisateur veut: commander un produit, 
        poser une question sur un produit, modifier sa commande, 
        ou a besoin d'aide.
        
        Tu es capable de détecter:
        - Les demandes de commande (ex: "Je veux commander", "J'ai besoin de")
        - Les questions produits (ex: "C'est quoi le prix de", "Vous avez")
        - Les modifications de panier (ex: "Enlève", "Ajoute encore", "Change la quantité")
        - Les demandes de suivi (ex: "Où en est ma commande", "Statut de commande")
        - Les demandes d'aide (ex: "Comment ça marche", "Aide")
        
        Tu extrais aussi les entités importantes: produits mentionnés, quantités, dates.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )


def create_strategist_agent(llm) -> Agent:
    """
    Agent Strategist : Gestionnaire de commande et panier.
    Responsable d'assister l'utilisateur dans le processus d'achat.
    """
    return Agent(
        role='Gestionnaire de commande',
        goal='Assister l\'utilisateur dans le processus d\'achat',
        backstory="""Spécialiste en vente et gestion de panier.
        
        Tu guides l'utilisateur à travers le processus de commande:
        - Tu suggères des produits pertinents basés sur le contexte
        - Tu gères l'ajout/suppression d'articles au panier
        - Tu valides les quantités et unités de mesure
        - Tu calcules les totaux
        - Tu proposes des produits complémentaires si approprié
        - Tu vérifies que la commande est complète avant validation
        
        Tu connais le catalogue de produits (eau Oulmes, boissons) et 
        les règles métier (quantités minimales, unités de mesure acceptées).""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )


def create_communicator_agent(llm) -> Agent:
    """
    Agent Communicator : Interface client.
    Responsable de la rédaction des messages WhatsApp.
    """
    return Agent(
        role='Communicateur client',
        goal='Rédiger des messages clairs, sympathiques et professionnels',
        backstory="""Tu es l'interface client. Tu transformes les actions 
        techniques en messages compréhensibles et agréables.
        Tu connais le contexte de la conversation.
        
        Ton style de communication:
        - Utilise un ton amical mais professionnel (B2B)
        - Sois concis et précis
        - Utilise des emojis appropriés (📦 pour produits, ✅ pour confirmation, 🛒 pour panier)
        - Structure bien les informations (listes à puces, numérotation)
        - Confirme toujours les actions importantes
        - Pose des questions de clarification si nécessaire
        
        Tu adaptes ton message selon l'étape du processus:
        - Accueil chaleureux pour nouveaux utilisateurs
        - Confirmation claire pour les commandes
        - Messages d'erreur empathiques et constructifs""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )


def create_integrator_agent(llm, tools: list) -> Agent:
    """
    Agent Integrator : Connecteur système.
    Responsable des interactions avec la base de données et systèmes externes.
    """
    return Agent(
        role='Connecteur système',
        goal='Exécuter les actions sur les systèmes backend de manière fiable',
        backstory="""Spécialiste en intégration de systèmes.
        
        Tu es responsable de toutes les interactions avec:
        - La base de données Selfcare (clients, produits, commandes)
        - Le système de gestion de panier (Redis)
        - Les validations métier
        
        Tu t'assures que:
        - Les données sont valides avant insertion
        - Les erreurs sont capturées et remontées clairement
        - Les transactions sont atomiques
        - Les règles métier sont respectées (dates, quantités, autorisations)
        
        Tu utilises les outils mis à disposition et retournes des résultats
        structurés pour que les autres agents puissent agir.""",
        verbose=True,
        allow_delegation=False,
        tools=tools,
        llm=llm
    )


class AgentFactory:
    """Factory pour créer les agents avec leur configuration."""
    
    def __init__(self):
        """Initialise la factory avec le LLM Mistral."""
        logger.info(f"🤖 Initialisation des agents avec {settings.mistral_model}")
        self.llm = create_llm()
    
    def create_agents(self, tools: list = None) -> dict:
        """
        Crée tous les agents nécessaires.
        
        Args:
            tools: Liste des outils à fournir à l'agent Integrator
            
        Returns:
            Dictionnaire contenant les 4 agents
        """
        tools = tools or []
        
        agents = {
            'analyst': create_analyst_agent(self.llm),
            'strategist': create_strategist_agent(self.llm),
            'communicator': create_communicator_agent(self.llm),
            'integrator': create_integrator_agent(self.llm, tools)
        }
        
        logger.info(f"✅ {len(agents)} agents créés avec succès")
        return agents
