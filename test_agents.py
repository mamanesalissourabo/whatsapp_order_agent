"""Script de test pour valider la création des agents CrewAI."""

import sys
from pathlib import Path

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

try:
    from crew.agents import AgentFactory
    
    print("🤖 Test de création des agents CrewAI\n")
    print("=" * 60)
    
    # Créer la factory
    factory = AgentFactory()
    
    # Créer les agents
    agents = factory.create_agents(tools=[])
    
    print(f"\n✅ {len(agents)} agents créés avec succès!\n")
    
    # Afficher les détails de chaque agent
    for name, agent in agents.items():
        print(f"📋 Agent: {name.upper()}")
        print(f"   Role: {agent.role}")
        print(f"   Goal: {agent.goal[:80]}...")
        print(f"   Tools: {len(agent.tools) if hasattr(agent, 'tools') and agent.tools else 0}")
        print()
    
    print("=" * 60)
    print("✅ Test réussi! Les agents sont correctement configurés.")
    
except ImportError as e:
    print(f"❌ Erreur d'import: {e}")
    print("\n💡 Assurez-vous d'avoir installé les dépendances:")
    print("   pip install -r requirements.txt")
except Exception as e:
    print(f"❌ Erreur: {e}")
    import traceback
    traceback.print_exc()
