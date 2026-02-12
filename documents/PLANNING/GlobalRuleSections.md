The Obsidian AI Agent project (which we'll really start building in Module 3) has an excellent CLAUDE.md (`EXAMPLE_CLAUDE.md`) that demonstrates Layer 1 planning. It includes:

### 1. Core Principles:

TYPE SAFETY IS NON-NEGOTIABLE (strict mypy enforcement)
KISS (Keep It Simple, Stupid)
YAGNI (You Aren't Gonna Need It)

### 2. Tech Stack Decisions:

Backend: FastAPI + Pydantic AI
Language: Python 3.12 with UV package manager
Linting: Ruff + mypy (strict mode)
Logging: Structlog (AI-optimized structured logging)

### 3. Architecture Patterns:

Vertical slice architecture (tools/ directory)
OpenAI-compatible API layer
Tool-based agent design with Pydantic AI

### 4. Documentation Standards:

Google-style docstrings for code
Agent-optimized tool docstrings (special format for LLMs)
Performance notes in tool docs (token usage, execution time)

### 5. Logging Rules:

Structured logging with keyword arguments only
AI-readable context (correlation_id, source, duration_ms)
Exception logging with full stack traces

### 6. Testing Patterns:

Tests mirror source directory structure
Unit tests marked with @pytest.mark.unit
Integration tests in tests/integration/

This CLAUDE.md becomes the permanent foundation AI uses for all code in that project. We'll examine it in detail in Module 3.