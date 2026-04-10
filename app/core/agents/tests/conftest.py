"""Shared factories and fixtures for ``app/core/agents/tests/``.

Introduced in AI-6.4/6.5. Provides:

* ``make_agent_result`` — builds ``AgentResult`` with permissive defaults.
* ``make_skill_meta`` — builds ``SkillMeta`` with permissive defaults.
* ``tmp_skill_dir`` — writes a ``skills/{transit,knowledge,vault}/`` tree
  under ``tmp_path`` for loader tests.
* ``_reset_skill_cache`` — ``autouse`` fixture that clears the module-level
  skill cache before and after every test (mirrors
  ``app/core/agents/tests/test_metrics.py``'s ``_reset_singleton`` idiom).
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from app.core.agents.agent_result import AgentResult
from app.core.agents.evals.schemas import EvalCase, QualityCriterion
from app.core.agents.skill_loader import SkillMeta, clear_cache


def make_agent_result(**overrides: Any) -> AgentResult:
    """Return an ``AgentResult`` with safe defaults for tests."""
    defaults: dict[str, Any] = {
        "content": "ok",
        "confidence": 0.9,
        "warnings": (),
        "tools_used": (),
        "domain": "unified",
    }
    defaults.update(overrides)
    return AgentResult(**defaults)


def make_skill_meta(**overrides: Any) -> SkillMeta:
    """Return a ``SkillMeta`` with safe defaults for tests."""
    defaults: dict[str, Any] = {
        "name": "test_skill",
        "priority": 2,
        "token_cost": 100,
        "version": 1,
        "keywords": ("test",),
        "domain": "transit",
    }
    defaults.update(overrides)
    return SkillMeta(**defaults)


@pytest.fixture
def tmp_skill_dir(tmp_path: Path) -> Path:
    """Create a ``skills/{transit,knowledge,vault}/`` tree and return the root."""
    root = tmp_path / "skills"
    for domain in ("transit", "knowledge", "vault"):
        (root / domain).mkdir(parents=True, exist_ok=True)
    return root


@pytest.fixture(autouse=True)
def _reset_skill_cache() -> Generator[None, None, None]:
    """Clear the module-level skill cache before and after every test."""
    clear_cache()
    yield
    clear_cache()


# --- AI-7.1 eval case factories -----------------------------------------


def make_quality_criterion(**overrides: Any) -> QualityCriterion:
    """Return a ``QualityCriterion`` with safe defaults for tests."""
    defaults: dict[str, Any] = {
        "name": "factual_accuracy",
        "description": "Stub description for tests.",
    }
    defaults.update(overrides)
    return QualityCriterion(**defaults)


def make_eval_case(**overrides: Any) -> EvalCase:
    """Return an ``EvalCase`` with safe defaults for tests (5 stub criteria)."""
    defaults: dict[str, Any] = {
        "id": "test_001",
        "prompt": "Test prompt",
        "language": "lv",
        "expected_domain": "transit",
        "expected_tools": ("query_bus_status",),
        "quality_criteria": tuple(make_quality_criterion(name=f"criterion_{i}") for i in range(5)),
        "notes": "",
    }
    defaults.update(overrides)
    return EvalCase(**defaults)


@pytest.fixture
def tmp_eval_dir(tmp_path: Path) -> Path:
    """Create an empty ``cases/`` directory under ``tmp_path`` and return it."""
    root = tmp_path / "cases"
    root.mkdir(parents=True, exist_ok=True)
    return root
