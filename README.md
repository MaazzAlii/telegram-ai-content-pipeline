# Telegram AI Content Pipeline (v1)

A human-in-the-loop content automation system for Telegram channels built on n8n and Google Sheets.

```
RESEARCH → AI DRAFT → GOOGLE SHEETS QUEUE → HUMAN REVIEW (APPROVE) → SCHEDULE → TELEGRAM PUBLISH
```

## Quick Start (Local Setup)

### 1. Requirements
- Docker Desktop running locally
- Google Cloud Service Account (with Google Sheets API enabled)
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Gemini or OpenAI API Key

### 2. Start n8n
```bash
docker compose up -d
```
Access n8n at: `http://localhost:5678`

### 3. Folder Structure
```
telegram-ai-content-pipeline/
├── docker-compose.yml        # n8n local container definition with persistent volume
├── .env.example              # template of required environment variables
├── .gitignore                # prevents secrets, JSON keys, and local data from being committed
├── config/
│   └── sources.yaml          # Curated RSS and source endpoints per category
├── prompts/                  # Category-specific prompt templates (strict JSON)
│   ├── ai_news.md
│   ├── top10_prompts.md
│   └── ...
├── workflows/                # Exported n8n workflow definitions
│   ├── A-research.json
│   ├── B-drafting.json
│   ├── C-scheduling.json
│   └── D-publishing.json
├── scripts/                  # Helper scripts & dependencies
│   └── requirements.txt
└── README.md
```
