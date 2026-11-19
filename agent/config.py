import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("AUDIT_DATA_DIR", ROOT / "data"))
REGISTRY = ROOT / "config" / "source_registry.yaml"
OUT_DIR = Path(os.environ.get("AUDIT_OUT_DIR", ROOT / "out"))
HAND_CHECKS = ROOT / "eval" / "hand_checks"
CACHE_DIR = ROOT / "data" / "cache"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://audit:audit@localhost:55433/audit")

# Sarvam -- hosts Deepseek (generic reasoning) + Sarvam's own conversational model,
# plus a separate structured-decision endpoint (Prism). See agent/llm.py.
SARVAM_API_KEY = os.environ.get("SARVAM_API_KEY", "")
SARVAM_BASE_URL = os.environ.get("SARVAM_BASE_URL", "https://api.sarvam.ai/v2")
SARVAM_MODEL_REASONING = os.environ.get("SARVAM_MODEL_REASONING", "deepseekv4.1-flash-1017")
SARVAM_MODEL_CONVERSATIONAL = os.environ.get("SARVAM_MODEL_CONVERSATIONAL", "sarvam-105b-conversations")
SARVAM_MODEL_DECISION = os.environ.get("SARVAM_MODEL_DECISION", "sarvam-prism")
