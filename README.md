# GooseFlight Bot

Cliente de Telegram para controlar Goose remoto.

## Setup rápido

```bash
cd ~/gooseflight-bot
source .venv/bin/activate

# Configurar
cp .env.example .env
# editar .env con tus valores

# Ejecutar
python -m app.main
```

## Variables de entorno (.env)

```
TELEGRAM_BOT_TOKEN=tu_token_aqui
AUTHORIZED_USER_ID=tu_user_id_numerico
GOOSED_URL=http://localhost:3004
GOOSE_SECRET=tu_secret_key
```

## Desarrollo

```bash
source .venv/bin/activate
ruff check app/
pytest tests/ -v
```
