import ast
import operator
import os
import time
from dataclasses import dataclass
from typing import Dict, Optional

import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

# ============================================================
#   ██████╗ ███████╗███████╗███╗   ██╗
#  ██╔═══██╗╚══███╔╝██╔════╝████╗  ██║
#  ██║   ██║  ███╔╝ █████╗  ██╔██╗ ██║
#  ██║   ██║ ███╔╝  ██╔══╝  ██║╚██╗██║
#  ╚██████╔╝███████╗███████╗██║ ╚████║
#   ╚═════╝ ╚══════╝╚══════╝╚═╝  ╚═══╝
#   O Z E N   C O N F I G   S E C T I O N
# ============================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "apifreellm").strip().lower()

APIFREELLM_API_KEY = os.getenv("APIFREELLM_API_KEY", "")
APIFREELLM_BASE_URL = os.getenv("APIFREELLM_BASE_URL", "https://api.apifreellm.com/v1")
APIFREELLM_MODEL = os.getenv("APIFREELLM_MODEL", "gpt-4o-mini")
APIFREELLM_COOLDOWN_SECONDS = int(os.getenv("APIFREELLM_COOLDOWN_SECONDS", "25"))

CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY", "")
CEREBRAS_BASE_URL = os.getenv("CEREBRAS_BASE_URL", "https://api.cerebras.ai/v1")
CEREBRAS_MODEL = os.getenv("CEREBRAS_MODEL", "llama3.1-8b")
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
# ============================================================

SYSTEM_PROMPT = (
    "You are Ozen, a minimal, helpful Telegram AI assistant. "
    "Keep answers concise, practical, and friendly."
)


@dataclass
class ChatSettings:
    provider: str = DEFAULT_PROVIDER
    model: Optional[str] = None


CHAT_SETTINGS: Dict[int, ChatSettings] = {}
LAST_APIFREE_REQUEST_AT: Dict[int, float] = {}


SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
}


def get_chat_settings(chat_id: int) -> ChatSettings:
    if chat_id not in CHAT_SETTINGS:
        CHAT_SETTINGS[chat_id] = ChatSettings()
    return CHAT_SETTINGS[chat_id]


def safe_eval_math(expression: str) -> float:
    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in SAFE_OPERATORS:
            return SAFE_OPERATORS[type(node.op)](_eval(node.operand))
        raise ValueError("Only simple math expressions are allowed.")

    tree = ast.parse(expression, mode="eval")
    return _eval(tree.body)


def apifree_cooldown_remaining(chat_id: int) -> int:
    if chat_id not in LAST_APIFREE_REQUEST_AT:
        return 0
    elapsed = time.time() - LAST_APIFREE_REQUEST_AT[chat_id]
    remaining = APIFREELLM_COOLDOWN_SECONDS - int(elapsed)
    return max(0, remaining)


def call_apifreellm(model: str, user_message: str) -> str:
    if not APIFREELLM_API_KEY:
        return "APIFreeLLM API key is missing. Set APIFREELLM_API_KEY in your .env file."

    url = f"{APIFREELLM_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {APIFREELLM_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.4,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


def call_cerebras_minimal(model: str, user_message: str) -> str:
    """Minimal Cerebras request path: small payload, single-shot completion."""
    if not CEREBRAS_API_KEY:
        return "Cerebras API key is missing. Set CEREBRAS_API_KEY in your .env file."

    url = f"{CEREBRAS_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {CEREBRAS_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 300,
        "temperature": 0.2,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"].strip()


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi, I am Ozen 🤖\n"
        "Commands:\n"
        "/start - Welcome\n"
        "/math <expr> - Quick calculator\n"
        "/usage - Provider/model/cooldown info\n"
        "/model [name] - Show or set model\n"
        "/provider [apifreellm|cerebras] - Show or set provider"
    )


async def math_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /math 2*(3+5)")
        return
    expr = " ".join(context.args)
    try:
        result = safe_eval_math(expr)
        await update.message.reply_text(f"🧮 {expr} = {result}")
    except Exception as exc:
        await update.message.reply_text(f"Math error: {exc}")


async def usage_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)
    model = settings.model or (APIFREELLM_MODEL if settings.provider == "apifreellm" else CEREBRAS_MODEL)
    cooldown_left = apifree_cooldown_remaining(chat_id)

    await update.message.reply_text(
        f"Provider: {settings.provider}\n"
        f"Model: {model}\n"
        f"APIFreeLLM cooldown: {APIFREELLM_COOLDOWN_SECONDS}s\n"
        f"Cooldown remaining (this chat): {cooldown_left}s"
    )


async def model_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)

    if not context.args:
        current_model = settings.model or (APIFREELLM_MODEL if settings.provider == "apifreellm" else CEREBRAS_MODEL)
        await update.message.reply_text(f"Current model: {current_model}")
        return

    settings.model = " ".join(context.args).strip()
    await update.message.reply_text(f"Model updated to: {settings.model}")


async def provider_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    settings = get_chat_settings(chat_id)

    if not context.args:
        await update.message.reply_text(f"Current provider: {settings.provider}")
        return

    requested = context.args[0].strip().lower()
    if requested not in {"apifreellm", "cerebras"}:
        await update.message.reply_text("Provider must be 'apifreellm' or 'cerebras'.")
        return

    settings.provider = requested
    await update.message.reply_text(f"Provider set to: {requested}")


async def chat_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return

    chat_id = update.effective_chat.id
    user_text = update.message.text.strip()
    settings = get_chat_settings(chat_id)

    model = settings.model or (APIFREELLM_MODEL if settings.provider == "apifreellm" else CEREBRAS_MODEL)

    try:
        if settings.provider == "apifreellm":
            cooldown = apifree_cooldown_remaining(chat_id)
            if cooldown > 0:
                await update.message.reply_text(
                    f"⏳ APIFreeLLM has a {APIFREELLM_COOLDOWN_SECONDS}s cooldown. "
                    f"Please wait {cooldown}s."
                )
                return

            reply = call_apifreellm(model=model, user_message=user_text)
            LAST_APIFREE_REQUEST_AT[chat_id] = time.time()
        else:
            reply = call_cerebras_minimal(model=model, user_message=user_text)

        await update.message.reply_text(reply)
    except requests.HTTPError as exc:
        details = ""
        if exc.response is not None:
            details = f"\nResponse: {exc.response.text[:500]}"
        await update.message.reply_text(f"Provider HTTP error: {exc}{details}")
    except Exception as exc:
        await update.message.reply_text(f"Error: {exc}")


def validate_required_config() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN in environment.")
    if DEFAULT_PROVIDER not in {"apifreellm", "cerebras"}:
        raise RuntimeError("DEFAULT_PROVIDER must be 'apifreellm' or 'cerebras'.")


def main() -> None:
    validate_required_config()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("math", math_cmd))
    app.add_handler(CommandHandler("usage", usage_cmd))
    app.add_handler(CommandHandler("model", model_cmd))
    app.add_handler(CommandHandler("provider", provider_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat_handler))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
