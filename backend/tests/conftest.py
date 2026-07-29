import os

# Set dummy secrets before any module-level import triggers load_dotenv().
# Tests mock the actual API calls, so the key values don't matter — they just
# need to be non-empty so the Anthropic/Browserbase clients initialize without error.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-key")
os.environ.setdefault("BROWSERBASE_API_KEY", "test-bb-key")
os.environ.setdefault("BROWSERBASE_PROJECT_ID", "test-project")
os.environ.setdefault("SUPABASE_URL", "")
os.environ.setdefault("SUPABASE_KEY", "")
