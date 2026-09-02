"""pytest configuration — makes the SDK package importable for tests.

Additive: does not modify existing conftest behavior or project config.
"""
import sys
from pathlib import Path

_sdk_path = str(Path(__file__).resolve().parent.parent / "sdk")
if _sdk_path not in sys.path:
    sys.path.insert(0, _sdk_path)
