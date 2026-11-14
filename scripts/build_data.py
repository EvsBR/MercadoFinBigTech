#!/usr/bin/env python3
"""Atalho mantido por compatibilidade: o pipeline agora fica em pipeline/.
Equivale a `python -m pipeline.construir` (aceita --demo e --offline)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.construir import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
