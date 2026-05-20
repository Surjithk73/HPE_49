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

# Gemini API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

# App Settings
MAX_ROWS = int(os.getenv("MAX_ROWS", "10000"))
QUERY_TIMEOUT_SECONDS = int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.95"))
AUDIT_LOG_PATH = os.getenv("AUDIT_LOG_PATH", "audit/query_log.db")
SCHEMA_YAML_PATH = os.getenv("SCHEMA_YAML_PATH", "schema_store/enriched_schema.yaml")
FEW_SHOTS_PATH = os.getenv("FEW_SHOTS_PATH", "few_shots/examples.yaml")

# Allowed DB users and Max Cost Limits
ALLOWED_DB_USERS = [u.strip() for u in os.getenv("ALLOWED_DB_USERS", "querycraft_user").split(",") if u.strip()]
MAX_QUERY_COST = float(os.getenv("MAX_QUERY_COST", "10000.0"))


# Validation - ensure critical keys are present
required_vars = {
    "DB_HOST": DB_HOST,
    "DB_PORT": DB_PORT,
    "DB_NAME": DB_NAME,
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
    "GEMINI_API_KEY": GEMINI_API_KEY,
    "GEMINI_MODEL": GEMINI_MODEL,
}

missing_vars = [key for key, value in required_vars.items() if not value]
if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Build PostgreSQL connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
