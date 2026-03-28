# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup & Commands

### Environment Setup
```cmd
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env
# Fill in required secrets: MISTRAL_API_KEY, WHATSAPP_ACCESS_TOKEN, etc.
```

### Running the Application
```bash
# Start development server with hot reload
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload

# Access at http://localhost:8001
# API docs: http://localhost:8001/docs
```

### Running Tests
```bash
# Test agents initialization
python test_agents.py

# Test configuration loading
python test_config.py
```

### Tunnel for Local Testing (WhatsApp Webhook)
```bash
# Use ngrok or similar to expose local server to Meta
python run_with_tunnel.py
```

## Architecture Overview

### Core Components

**WhatsApp Order Agent** is a multi-agent conversational AI system (CrewAI) for product ordering via WhatsApp. It receives messages through the WhatsApp Business API webhook and routes them through a sophisticated 4-agent workflow.

### Data Flow
1. **WebHook Reception** (`app/main.py`): FastAPI receives WhatsApp messages via `/webhooks/whatsapp` endpoint
2. **Session Management** (`tools/session_manager.py`): Retrieves or creates user session (stores conversation history, cart state, client info) using Redis with fallback to in-memory storage
3. **Message Processing** (`app/main.py` → `process_incoming_message`):
   - Detects greetings vs. regular queries
   - For greetings: returns welcome message
   - For queries: invokes Mistral AI directly with conversation history (simplified flow without CrewAI crew orchestration)
4. **Response**(`tools/whatsapp_sender.py`): Sends formatted response back via WhatsApp API
5. **Session Persistence**: Updates and saves session history (maintains last 5 messages)

### The 4-Agent System (CrewAI)

Note: The CrewManager exists but is not currently actively used in the main flow. Message processing currently uses direct Mistral AI calls. CrewManager can be activated by calling `get_crew_manager().process_message()` in place of the direct LLM invocation.

**Analyst Agent**: Intention detection
- Identifies intent: order, question, cart modification, order tracking, help request
- Extracts entities (products, quantities, dates)

**Strategist Agent**: Order & cart management
- Guides through purchase process
- Manages cart operations (add, remove items)
- Validates quantities and business rules
- Calculates totals, suggests complementary products

**Communicator Agent**: Client-facing interface
- Transforms technical actions into friendly WhatsApp messages
- Uses emojis, clear formatting, proper structure
- Provides empathetic error messages

**Integrator Agent**: System backend connector
- Executes actions on external systems:
  - Selfcare database (customers, products, orders) via SQLAlchemy
  - Cart management (Redis)
  - Business rule validation
- Only agent with tool access for DB operations

### Key Tools Available

- **SearchProductsTool**: Query Selfcare database for products, prices, availability
- **AddToCartTool** / **RemoveFromCartTool** / **ViewCartTool**: Cart operations managed in Redis
- **SendWhatsAppMessageTool**: Send WhatsApp messages via Meta API

### Configuration & Settings

All app settings are loaded from `.env` via `config/settings.py` (Pydantic BaseSettings):
- **Mistral AI**: API key, model name (default: mistral-small-latest), temperature, max_tokens
- **WhatsApp**: Access token, verify token, phone number ID, API base URL
- **Database**: Selfcare PostgreSQL connection string
- **Redis**: Connection URL, session TTL (30 minutes default)
- **App**: Host, port, debug flag, logging level
- **Session**: Max conversation history length (default: 5 messages)

### Database

**Selfcare PostgreSQL**: ORM models in `database/models.py`
- Stores customers, products, orders, order items
- Connected via SQLAlchemy with psycopg2 driver
- Session manager caches user data in Redis

## Project Structure

```
whatsapp_order_agent/
├── app/
│   ├── main.py                 # FastAPI app, webhook endpoints, message processing
│   └── __init__.py
├── crew/
│   ├── agents.py              # AgentFactory, agent definitions
│   ├── crew_manager.py        # CrewManager singleton for multi-agent orchestration
│   ├── tasks.py               # Task definitions for agents
│   └── __init__.py
├── tools/
│   ├── product_search.py      # SearchProductsTool (DB queries)
│   ├── cart_manager.py        # Cart tools (add, remove, view)
│   ├── session_manager.py     # Session & conversation history management
│   ├── whatsapp_sender.py     # WhatsApp API wrapper
│   └── __init__.py
├── database/
│   ├── connection.py          # SQLAlchemy setup, session management
│   ├── models.py              # ORM models (Customer, Product, Order, etc.)
│   └── __init__.py
├── config/
│   ├── settings.py            # Pydantic Settings configuration
│   └── __init__.py
├── schemas/
│   ├── messages.py            # WhatsAppWebhookPayload, message models
│   ├── orders.py              # Order-related schemas
│   ├── products.py            # Product schemas
│   ├── sessions.py            # Session/conversation schemas
│   └── __init__.py
├── requirements.txt           # Python dependencies
├── .env.example               # Environment template
├── test_agents.py            # Agent initialization tests
├── test_config.py            # Configuration tests
├── run_with_tunnel.py        # Tunnel setup for local testing
└── CLAUDE.md                 # This file
```

## Important Design Decisions

### Conversation History
- Stored in Redis with 30-minute TTL per session (user phone number)
- Fallback to in-memory storage if Redis unavailable
- Limited to 5 messages by default (configurable via `MAX_CONVERSATION_HISTORY`)
- Used to provide context for LLM responses
- Session data includes: chat history, client name, phone number, cart state

### Language Model
- Uses Mistral AI (mistral-small-latest), not GPT
- Temperature set to 0.7 for balanced responses
- Direct Mistral calls in main flow (simpler than full CrewAI pipeline)
- System prompt emphasizes French language, direct responses, no preambles

### WhatsApp Integration
- Webhook-based (Meta pushes messages to us)
- Async processing: returns 200 immediately, processes in background
- Always returns 200 to Meta to avoid retries
- Messages sent via Meta Graph API (v18.0)
- Greeting detection includes: salut, bonjour, coucou, hello, hi, hey, ça va, comment allez

### Fallback Strategy
- Redis unavailable: uses in-memory session storage
- Mistral API errors: sends generic error message to user
- Invalid database connection: handled in tool execution

## Common Development Tasks

### Adding a New Tool
1. Create class inheriting from CrewAI's `BaseTool` in `tools/`
2. Define `name`, `description`, and `func()/async_func()` methods
3. Add to imports in `tools/__init__.py`
4. Include in tools list passed to CrewManager initialization in `app/main.py`

### Adding a New Agent
1. Add agent creation function in `crew/agents.py`
2. Add to `AgentFactory.create_agents()` return dictionary
3. Define corresponding tasks in `crew/tasks.py` if using CrewManager flow

### Testing Message Processing
- Use `test_agents.py` as template for initialization tests
- Remember: main flow uses direct Mistral, not CrewManager
- For CrewManager testing, call `get_crew_manager().process_message()` with message, phone_number, context dict

### Debugging Sessions
- Check Redis: `redis-cli` → `KEYS *` to see session keys
- Session keys format: `session:{phone_number}`
- Session structure: `{history: [...], client_name: str, phone_number: str}`
