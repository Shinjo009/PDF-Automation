"""Pytest path bootstrap for modules.bioai_report imports."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _ensure_namespace(name: str) -> types.ModuleType:
    parts = name.split(".")
    for i in range(1, len(parts) + 1):
        mod_name = ".".join(parts[:i])
        if mod_name not in sys.modules:
            pkg = types.ModuleType(mod_name)
            pkg.__path__ = []  # type: ignore[attr-defined]
            sys.modules[mod_name] = pkg
    return sys.modules[name]


def _load_module(qualified_name: str, file_path: Path) -> types.ModuleType:
    if qualified_name in sys.modules:
        return sys.modules[qualified_name]
    parent = ".".join(qualified_name.split(".")[:-1])
    if parent:
        _ensure_namespace(parent)
    spec = importlib.util.spec_from_file_location(qualified_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {qualified_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified_name] = module
    spec.loader.exec_module(module)
    return module


_ensure_namespace("modules")
_ensure_namespace("modules.bioai_report")
_ensure_namespace("modules.bioai_report.pdf_renderer")

_load_module(
    "modules.bioai_report.pdf_renderer.report_store",
    ROOT / "pdf_renderer" / "report_store.py",
)
_load_module(
    "modules.bioai_report.pdf_renderer.exceptions",
    ROOT / "pdf_renderer" / "exceptions.py",
)
_load_module(
    "modules.bioai_report.pdf_renderer.greeting_cards",
    ROOT / "pdf_renderer" / "greeting_cards.py",
)
