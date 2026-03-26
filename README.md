# WhatsApp Order Agent - Agent IA B2B

Agent conversationnel multi-agents (CrewAI) pour la prise de commandes B2B via WhatsApp.

## Architecture

L'application utilise une architecture multi-agents avec 4 agents spécialisés :

- **Analyst** : Analyse les intentions de l'utilisateur (commander, questionner, modifier, aide)
- **Strategist** : Gestionnaire de commande, spécialiste en vente et gestion de panier
- **Communicator** : Interface client qui rédige des messages clairs et sympathiques
- **Integrator** : Connecteur vers la base de données Selfcare et systèmes externes

## Structure du projet

```
whatsapp_order_agent/
├── app/              # Application FastAPI
├── crew/             # Définition des agents et tâches CrewAI
├── tools/            # Outils pour les agents (accès DB, WhatsApp)
├── config/           # Configuration de l'application
├── database/         # Connexion et modèles de base de données
├── schemas/          # Schémas Pydantic
└── requirements.txt  # Dépendances Python
```

## Installation

### 1. Créer un environnement virtuel

```bash
cd C:\src\Django_tuto\whatsapp_order_agent
python -m venv venv
venv\Scripts\activate  # Windows
```

### 2. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 3. Configuration

Copier `.env.example` vers `.env` et renseigner les variables :

```bash
copy .env.example .env
```

#### Obtenir une clé API Mistral (gratuite)

1. Créer un compte sur [console.mistral.ai](https://console.mistral.ai)
2. Générer une clé API dans la section "API Keys"
3. Copier la clé dans `MISTRAL_API_KEY`

#### Configuration WhatsApp Business API

1. Créer un compte Meta Developer : [developers.facebook.com](https://developers.facebook.com)
2. Créer une application WhatsApp Business
3. Obtenir le Phone Number ID et Access Token
4. Définir un verify token personnalisé

### 4. Configuration Redis (optionnel pour développement)

Redis est utilisé pour gérer les sessions conversationnelles.

**Option A - Redis local :**
```bash
# Télécharger Redis pour Windows depuis https://github.com/microsoftarchive/redis/releases
# Lancer redis-server.exe
```

**Option B - Redis Docker :**
```bash
docker run -d -p 6379:6379 redis:alpine
```

## Utilisation

### Démarrer le serveur

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

L'API sera accessible sur : http://localhost:8001

Documentation Swagger : http://localhost:8001/docs

## Prochaines étapes

1. ✅ Initialisation de la structure du projet
2. ⏳ Configuration de l'application FastAPI
3. ⏳ Création des agents CrewAI
4. ⏳ Développement des outils d'accès à Selfcare
5. ⏳ Implémentation du webhook WhatsApp
6. ⏳ Tests et déploiement

## Technologies

- **FastAPI** : Framework web asynchrone
- **CrewAI** : Framework multi-agents
- **Mistral AI** : Modèle de langage (mistral-small-latest)
- **SQLAlchemy** : ORM pour accès à PostgreSQL
- **Redis** : Gestion de sessions
- **Pydantic** : Validation de données
