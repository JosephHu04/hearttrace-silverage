"""Resolve configuration before any module creates a database engine."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def configure_environment() -> Path:
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env.local", override=False)
    load_dotenv(root / "services" / "api" / ".env", override=False)
    api = root / "services" / "api"
    if str(api) not in sys.path:
        sys.path.insert(0, str(api))
    os.chdir(api)
    return root
