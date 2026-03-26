"""
Gestionnaire de la Crew : Orchestration des agents pour traiter les messages WhatsApp.
"""

from crewai import Crew, Process
from crew.agents import AgentFactory
from crew.tasks import TaskFactory
from typing import Dict, Any
import logging
import json

logger = logging.getLogger(__name__)


class CrewManager:
    """
    Gestionnaire principal de la Crew d'agents.
    Orchestre le traitement des messages WhatsApp via les 4 agents spécialisés.
    """
    
    def __init__(self, tools: list = None):
        """
        Initialise le gestionnaire avec les agents et outils.
        
        Args:
            tools: Liste des outils à fournir à l'agent Integrator
        """
        logger.info("🎬 Initialisation du CrewManager")
        
        self.tools = tools or []
        self.agent_factory = AgentFactory()
        self.task_factory = TaskFactory()
        
        # Créer les agents
        self.agents = self.agent_factory.create_agents(tools=self.tools)
        
        logger.info(f"✅ CrewManager initialisé avec {len(self.agents)} agents")
    
    def process_message(
        self, 
        message: str, 
        phone_number: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Traite un message WhatsApp via la Crew d'agents.
        
        Args:
            message: Le message texte reçu de l'utilisateur
            phone_number: Numéro WhatsApp de l'utilisateur
            context: Contexte de la conversation (historique, panier, client, etc.)
            
        Returns:
            Dictionnaire avec la réponse et le contexte mis à jour
        """
        logger.info(f"📨 Traitement message de {phone_number}: {message[:50]}...")
        
        try:
            # Enrichir le contexte avec le numéro de téléphone
            full_context = {
                **context,
                'phone_number': phone_number,
                'current_message': message
            }
            
            # Créer les tâches pour ce message
            tasks = self.task_factory.create_conversation_tasks(
                self.agents,
                message,
                full_context
            )
            
            # Créer la Crew avec les agents et tâches
            crew = Crew(
                agents=list(self.agents.values()),
                tasks=tasks,
                process=Process.sequential,  # Exécution séquentielle
                verbose=True
            )
            
            logger.info("🚀 Lancement de la Crew...")
            
            # Exécuter la Crew
            result = crew.kickoff()
            
            logger.info("✅ Crew terminée avec succès")
            
            # Le résultat final est le message du Communicator
            response_message = str(result)
            
            return {
                "success": True,
                "message": response_message,
                "context": full_context  # Retourner le contexte pour mise à jour session
            }
            
        except Exception as e:
            logger.error(f"❌ Erreur lors du traitement de la Crew: {str(e)}", exc_info=True)
            
            # Message d'erreur générique pour l'utilisateur
            error_message = (
                "😔 Désolé, j'ai rencontré un problème technique. "
                "Pouvez-vous reformuler votre demande ou réessayer dans quelques instants?"
            )
            
            return {
                "success": False,
                "message": error_message,
                "error": str(e),
                "context": context
            }
    
    def get_agents_info(self) -> Dict[str, Dict[str, str]]:
        """
        Retourne les informations sur les agents configurés.
        Utile pour debugging et monitoring.
        """
        return {
            name: {
                'role': agent.role,
                'goal': agent.goal,
                'tools_count': len(agent.tools) if hasattr(agent, 'tools') else 0
            }
            for name, agent in self.agents.items()
        }


# Instance globale du CrewManager (sera initialisée au démarrage de l'app)
_crew_manager_instance = None


def get_crew_manager(tools: list = None) -> CrewManager:
    """
    Récupère ou crée l'instance singleton du CrewManager.
    
    Args:
        tools: Liste des outils (nécessaire uniquement à la première initialisation)
    """
    global _crew_manager_instance
    
    if _crew_manager_instance is None:
        _crew_manager_instance = CrewManager(tools=tools)
    
    return _crew_manager_instance
