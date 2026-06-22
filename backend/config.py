"""
Configuration loader for QueryCraft backend.
Loads all environment variables and exposes them as typed constants.
"""
import os
from dotenv import load_dotenv

# Load .env file (override system environment variables to ensure we use the file's API key)
load_dotenv(override=True)

# PostgreSQL Configuration
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")

# LLM Provider Configuration
# 'nvidia' (default, NVIDIA NIM) or 'ollama'. Ollama enables fully-offline SQL
# generation against a local model server; the chosen engine must satisfy the
# same generate_sql(prompt) interface (see pipeline/llm_engine.py).
LLM_PROVIDER = (os.getenv("LLM_PROVIDER") or "nvidia").lower()

# NVIDIA NIM Configuration (required when LLM_PROVIDER='nvidia')
# OpenAI-compatible endpoint; each model role carries its own API key.
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")

# Optional shared NVIDIA key used as a fallback when a role-specific key is unset.
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

# Model roles — PLANNER (clarification loop) and SQL_GENERATOR (SQL compilation).
# Each role runs on its own NVIDIA NIM model and its own API key (config only).
PLANNER_MODEL = os.getenv("PLANNER_MODEL", "z-ai/glm-5.1")
SQL_GENERATOR_MODEL = os.getenv("SQL_GENERATOR_MODEL", "deepseek-ai/deepseek-v4-pro")

PLANNER_API_KEY = os.getenv("PLANNER_API_KEY") or NVIDIA_API_KEY
SQL_GENERATOR_API_KEY = os.getenv("SQL_GENERATOR_API_KEY") or NVIDIA_API_KEY

# Vision model for the chart-image → NL-question endpoint (/api/upload-chart).
# Must be a multimodal NVIDIA NIM model; defaults to the planner model.
NVIDIA_VISION_MODEL = os.getenv("NVIDIA_VISION_MODEL", PLANNER_MODEL)

# Sampling — deterministic by default. Planner allows slight variation for
# clarification phrasing; the SQL generator stays at temperature 0.
PLANNER_TEMPERATURE = float(os.getenv("PLANNER_TEMPERATURE", "0.2"))
PLANNER_TOP_P = float(os.getenv("PLANNER_TOP_P", "0.9"))
SQL_GENERATOR_TEMPERATURE = float(os.getenv("SQL_GENERATOR_TEMPERATURE", "0.0"))
SQL_GENERATOR_TOP_P = float(os.getenv("SQL_GENERATOR_TOP_P", "1.0"))

# SQL dialect used by the generator prompt and the validator lint pass.
# postgres | sqlmx | sqlmp  (see backend/config/planner_defaults.yaml)
SQL_DIALECT = os.getenv("SQL_DIALECT", "postgres")

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

# Allowed DB users
ALLOWED_DB_USERS = [u.strip() for u in os.getenv("ALLOWED_DB_USERS", "querycraft_user").split(",") if u.strip()]


# Validation - ensure critical keys are present
required_vars = {
    "DB_HOST": DB_HOST,
    "DB_PORT": DB_PORT,
    "DB_NAME": DB_NAME,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
}

# Provider-specific requirements
if LLM_PROVIDER == "nvidia":
    required_vars["PLANNER_API_KEY"] = PLANNER_API_KEY
    required_vars["SQL_GENERATOR_API_KEY"] = SQL_GENERATOR_API_KEY
    required_vars["PLANNER_MODEL"] = PLANNER_MODEL
    required_vars["SQL_GENERATOR_MODEL"] = SQL_GENERATOR_MODEL
elif LLM_PROVIDER == "ollama":
    required_vars["OLLAMA_MODEL"] = OLLAMA_MODEL
else:
    raise ValueError(
        f"Unknown LLM_PROVIDER='{LLM_PROVIDER}'. Expected 'nvidia' or 'ollama'."
    )

missing_vars = [key for key, value in required_vars.items() if not value]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Build PostgreSQL connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
