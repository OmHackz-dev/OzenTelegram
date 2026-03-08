# Ozen Telegram AI Assistant

Minimal Telegram AI assistant named **Ozen** with:
- Default provider: **APIFreeLLM**
- Optional provider switch: **Cerebras Cloud**
- Commands: `/start`, `/math`, `/usage`, `/model`, `/provider`
- APIFreeLLM cooldown awareness (default **25 seconds**)

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy env template:
   ```bash
   cp .env.example .env
   ```
4. Fill `.env` values.
5. Run:
   ```bash
   python bot.py
   ```

## Commands

- `/start` - Show welcome + command list
- `/math 2*(3+5)` - Safe quick math evaluator
- `/usage` - Shows current provider/model + cooldown information
- `/model` - Show current model
- `/model <name>` - Set model for current chat
- `/provider` - Show current provider
- `/provider apifreellm` or `/provider cerebras` - Switch provider for current chat

## Notes

- APIFreeLLM cooldown is enforced per chat in memory.
- Provider/model settings are in-memory (reset when bot restarts).
- Cerebras path is intentionally minimal for quick responses.
