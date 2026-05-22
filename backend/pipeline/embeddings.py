"""
Shared embedding model for QueryCraft.

Both SemanticCache and SchemaLinker use BAAI/bge-large-en-v1.5. Loading it
twice wastes ~1.3 GB of RAM and several seconds of startup. This module owns
a single instance and hands it out to any caller.

The model loads in a background thread on first request so callers stay
non-blocking. Use `is_ready()` to check, or `get()` to fetch (returns None
until ready).
"""
import threading
from typing import Optional

from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-large-en-v1.5"

_model: Optional[SentenceTransformer] = None
_ready = threading.Event()
_load_lock = threading.Lock()
_load_started = False


def _load() -> None:
    global _model
    try:
        _model = SentenceTransformer(MODEL_NAME)
        _ready.set()
        print(f"[Embeddings] Model '{MODEL_NAME}' ready.")
    except Exception as e:
        print(f"[Embeddings] ERROR: failed to load model: {e}")


def start_loading() -> None:
    """Kick off the background load (idempotent)."""
    global _load_started
    with _load_lock:
        if _load_started:
            return
        _load_started = True
    print(f"[Embeddings] Loading '{MODEL_NAME}' in background...")
    threading.Thread(target=_load, name="embedding-loader", daemon=True).start()


def is_ready() -> bool:
    return _ready.is_set()


def get() -> Optional[SentenceTransformer]:
    """Return the model, or None if it isn't loaded yet."""
    return _model


def wait(timeout: Optional[float] = None) -> bool:
    """Block until the model is ready. Returns True if ready, False on timeout."""
    return _ready.wait(timeout=timeout)
