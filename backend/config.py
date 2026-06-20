# config.py — loads secrets from .env. Keys live ONLY here, never in the extension.
import os
from dotenv import load_dotenv

load_dotenv()

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY", "")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Supabase (optional) — persists user preferences. service_role key, backend only.
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
