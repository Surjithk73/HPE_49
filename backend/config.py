"""
Configuration loader for QueryCraft backend.
Loads all environment variables and exposes them as typed constants.
"""
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# PostgreSQL Configuration
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# LLM Provider Configuration
# 'gemini' (default) or 'ollama'. Ollama enables fully-offline SQL generation
# against a local model server; the chosen engine must satisfy the same
# generate_sql(prompt) interface (see pipeline/llm_engine.py).
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "gemini").lower()

# Gemini API Configuration (required when LLM_PROVIDER='gemini')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

# Ollama Configuration (required when LLM_PROVIDER='ollama')
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL")
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))

# App Settings
MAX_ROWS = int(os.getenv("MAX_ROWS", "10000"))
QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.95"))
AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "audit/query_log.db")
SCHEMA_YAML_PATH = os.getenv("SCHEMA_YAML_PATH", "schema_store/enriched_schema.yaml")
FEW_SHOTS_PATH = os.getenv("FEW_SHOTS_PATH", "few_shots/examples.yaml")

# Validation - ensure critical keys are present
required_vars = {
    "DB_HOST": DB_HOST,
    "DB_PORT": DB_PORT,
    "DB_NAME": DB_NAME,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
}

# Provider-specific requirements
if LLM_PROVIDER == "gemini":
    required_vars["GEMINI_API_KEY"] = GEMINI_API_KEY
    required_vars["GEMINI_MODEL"] = GEMINI_MODEL
elif LLM_PROVIDER == "ollama":
    required_vars["OLLAMA_MODEL"] = OLLAMA_MODEL
else:
    raise ValueError(
        f"Unknown LLM_PROVIDER='{LLM_PROVIDER}'. Expected 'gemini' or 'ollama'."
    )

missing_vars = [key for key, value in required_vars.items() if not value]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Build PostgreSQL connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
