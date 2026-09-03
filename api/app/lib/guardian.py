"""Guardian Layer（lib/schema_validator.py）のローダー。

api パッケージからはリポジトリルートの lib/ に import パスが通らず、
lib/__init__.py の import 連鎖（dotenv / streamlit）も避けたいので、
check_semantic_drift.py と同じくファイル直読みで 1 回だけロードする。
graph_validate.py と db_operations.py が共用する。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_SV_PATH = Path(__file__).resolve().parents[3] / "lib" / "schema_validator.py"
_spec = importlib.util.spec_from_file_location("guardian_schema_validator", _SV_PATH)
guardian = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guardian)

__all__ = ["guardian"]
