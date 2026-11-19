import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("AUDIT_DATA_DIR", ROOT / "data"))
REGISTRY = ROOT / "config" / "source_registry.yaml"
OUT_DIR = Path(os.environ.get("AUDIT_OUT_DIR", ROOT / "out"))
HAND_CHECKS = ROOT / "eval" / "hand_checks"
