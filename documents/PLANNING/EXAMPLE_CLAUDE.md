# AI Agent Development Instructions

## Project Overview

OpenAI-compatible API agent for Obsidian CoPilot using FastAPI + Pydantic AI, UV, Ruff + mypy (strict type safety), Structlog (AI-optimized logging), and vertical slice architecture.

## Core Principles

1. **TYPE SAFETY IS NON-NEGOTIABLE**
   - All functions, methods, and variables MUST have type annotations
   - Strict mypy configuration is enforced
   - No `Any` types without explicit justification

2. **KISS** (Keep It Simple, Stupid)
   - Prefer simple, readable solutions over clever abstractions

3. **YAGNI** (You Aren't Gonna Need It)
   - Don't build features until they're actually needed

**Architecture:**
```
src/
├── agent/    # Core orchestration
├── openai/   # OpenAI compatibility layer
├── tools/    # Independent slices (web_search, image_analysis, etc.)
└── shared/   # Cross-cutting (config, logging, middleware)
```

Each tool is a vertical slice containing tool.py, schemas.py, service.py.

---

## Documentation Style

**Use Google-style docstrings** for all functions, classes, and modules:

```python
def process_request(user_id: str, query: str) -> dict[str, Any]:
    """Process a user request and return results.

    Args:
        user_id: Unique identifier for the user.
        query: The search query string.

    Returns:
        Dictionary containing results and metadata.

    Raises:
        ValueError: If query is empty or invalid.
        ProcessingError: If processing fails after retries.
    """
```

---

## Tool Docstrings for Agents

**Critical Difference:** Tool docstrings are read by LLMs during tool selection. They must guide the agent to choose the RIGHT tool, use it EFFICIENTLY, and compose tools into workflows.

### Philosophy: Write for Agent Comprehension

Standard Google-style docstrings document **what code does** for human developers.
Agent tool docstrings guide **when to use the tool and how** for LLM reasoning.

**Key Principles:**

1. **Guide Tool Selection** - Agent must choose this tool over alternatives
2. **Prevent Token Waste** - Steer toward efficient parameter choices
3. **Enable Composition** - Show how tool fits into multi-step workflows
4. **Set Expectations** - Explain performance characteristics and limitations
5. **Provide Examples** - Concrete usage with realistic data

### Required Elements (MUST Include)

Every agent tool docstring MUST include these sections in order:

#### 1. One-Line Summary
Clear statement of the tool's primary purpose.

#### 2. Use This When (Affirmative Guidance)
3-5 bullet points describing specific scenarios where this tool is the right choice.

#### 3. Do NOT Use This For (Negative Guidance)
**CRITICAL:** Tell agent when to use OTHER tools instead. Prevents tool confusion.

#### 4. Args (Parameter Guidance)
- Each parameter with type and description (standard Google-style)
- **PLUS:** Explain WHY you'd choose different values
- For enums: describe each option's use case
- For optional params: guidance on when to include vs omit

#### 5. Returns
What the tool returns (standard), **PLUS** format/structure details.

#### 6. Performance Notes (NEW - Required for Tools)
- Token usage for different configurations (minimal vs detailed)
- Typical execution time
- Resource limits (max file size, result count)
- Cost implications (API calls, database queries)

#### 7. Examples (Concrete Usage)
2-4 realistic examples showing:
- Simple common case
- Complex case with multiple parameters
- Edge case or important variation
- Use realistic paths/data (not "foo", "bar", "test.md")

### Template Structure

```python
@agent.tool
async def tool_name(
    ctx: RunContext[AgentDependencies],
    param1: str,
    param2: int = 10,
    response_format: str = "concise"
) -> str:
    """[One-line summary of what this tool does].

    Use this when you need to:
    - [Specific scenario 1 where this tool is the right choice]
    - [Specific scenario 2]
    - [Specific scenario 3]

    Do NOT use this for:
    - [Scenario where OTHER_TOOL should be used instead]
    - [Scenario where ANOTHER_TOOL should be used instead]
    - [Anti-pattern or common misuse]

    Args:
        param1: [Standard description]
            Use this to [explain purpose and when to vary it].
        param2: [Standard description]. Range: 1-100.
            - Small values (1-10): [use case]
            - Medium values (10-50): [use case]
            - Large values (50+): [use case and warnings]
        response_format: Control output verbosity and token usage.
            - "minimal": [Description] (~50 tokens, use when [scenario])
            - "concise": [Description] (~150 tokens, default, balanced)
            - "detailed": [Description] (~1500+ tokens, use sparingly when [scenario])

    Returns:
        [Description of return value].
        Format: [Structure/format details that help agent parse].

    Performance Notes:
        - Minimal format: ~50 tokens (use for [scenario])
        - Concise format: ~150 tokens (default, good for most cases)
        - Detailed format: ~1500+ tokens (only when full content needed)
        - Typical execution time: [duration] for [scenario]
        - Max [resource limit]: [value] ([what happens if exceeded])
        - [Other performance characteristics]

    Examples:
        # [Brief description of what this example shows]
        tool_name(
            param1="projects/alpha.md",
            param2=5,
            response_format="minimal"
        )

        # [Description of complex case]
        tool_name(
            param1="research/ai-overview.md",
            param2=50,
            response_format="detailed"
        )

        # [Description of edge case or important variation]
        tool_name(
            param1="inbox/quick-note.md",
            param2=1,
            response_format="concise"
        )
    """
```

### Comparison: Standard vs Agent Tool Docstring

**❌ Standard Google-style (Insufficient for Agents):**
```python
def read_note(path: str, include_frontmatter: bool = True) -> str:
    """Read a note from the Obsidian vault.

    Args:
        path: Path to the note file.
        include_frontmatter: Whether to include YAML frontmatter.

    Returns:
        String containing the note content.

    Raises:
        FileNotFoundError: If note doesn't exist.
    """
```

**Problems:**
- No guidance on WHEN to use this vs other tools
- No token efficiency information
- No performance characteristics
- No examples with realistic data
- Agent doesn't know if this is for single notes or batches

**✅ Agent-Optimized Tool Docstring:**
```python
@agent.tool
async def obsidian_note_read(
    ctx: RunContext[AgentDependencies],
    path: str,
    response_format: str = "concise"
) -> str:
    """Read a single note from the Obsidian vault with token-efficient formatting.

    Use this when you need to:
    - View the content of a SPECIFIC note you already know the path to
    - Check metadata (tags, status, dates) from frontmatter
    - Verify a note exists before performing other operations
    - Read content to inform a follow-up action (update, summarize)

    Do NOT use this for:
    - Finding notes (use obsidian_vault_query with search instead)
    - Reading MULTIPLE notes at once (use obsidian_vault_query with batch mode)
    - Analyzing note relationships (use obsidian_graph_analyze instead)
    - Just checking if a note exists (use response_format="minimal")

    Args:
        path: Relative path from vault root.
            Examples: "daily/2025-01-15.md", "projects/alpha.md", "inbox/ideas.md"
            Do NOT include vault path - just the relative path within the vault.
        response_format: Control output verbosity to save tokens.
            - "minimal": Title, tags, summary only (~50 tokens)
                Use when: Just need to check metadata or verify existence
            - "concise": Key metadata + content preview (~150 tokens)
                Use when: Need overview before deciding next action (DEFAULT)
            - "detailed": Full content with all frontmatter (~1500+ tokens)
                Use when: Need complete content for summarization or analysis

    Returns:
        Formatted markdown string with note content.
        Minimal: Title, tags, modified date
        Concise: Above + first 100 words of content
        Detailed: Full content with complete frontmatter section

    Performance Notes:
        - Minimal format: ~50 tokens (recommended for metadata checks)
        - Concise format: ~150 tokens (default, good balance)
        - Detailed format: ~1500+ tokens (use only when truly needed)
        - Execution time: 10-50ms for typical notes
        - Max file size: 10MB (raises error if exceeded)
        - Always prefer concise over detailed to conserve tokens

    Examples:
        # Check if daily note exists and get its tags (minimal)
        obsidian_note_read(
            path="daily/2025-01-15.md",
            response_format="minimal"
        )

        # Get overview of project note before updating (concise - default)
        obsidian_note_read(
            path="projects/website-redesign.md",
            response_format="concise"
        )

        # Read full research note for comprehensive analysis (detailed)
        obsidian_note_read(
            path="research/ai-safety-overview.md",
            response_format="detailed"
        )

        # Quick metadata check on meeting notes
        obsidian_note_read(
            path="meetings/2025-01-15-standup.md",
            response_format="minimal"
        )
    """
```

**Why This Works:**
- **"Use this when"** → Agent knows when to select this tool
- **"Do NOT use"** → Prevents tool confusion, directs to better alternatives
- **Parameter guidance** → Agent understands WHY to choose each format
- **Performance notes** → Agent can optimize for token efficiency
- **Realistic examples** → Shows concrete usage patterns the agent can follow
- **Token costs explicit** → Agent sees 50 vs 1500+ token difference clearly

### Common Anti-Patterns (Avoid These)

**❌ Vague affirmative guidance:**
```python
"""Use this when you need to work with notes."""
```
Too generic. What KIND of work? Reading? Searching? Updating?

**✅ Specific affirmative guidance:**
```python
"""Use this when you need to:
- Read the content of a single known note
- Extract metadata from frontmatter for a specific file
- Verify a note exists at a specific path
"""
```

**❌ Missing negative guidance:**
```python
# No "Do NOT use this for" section
```
Agent doesn't know when to use other tools instead. High tool confusion risk.

**✅ Clear negative guidance:**
```python
"""Do NOT use this for:
- Searching for notes (use obsidian_vault_query instead)
- Batch reading (use obsidian_vault_query with batch mode)
- Graph analysis (use obsidian_graph_analyze instead)
"""
```

**❌ Toy examples:**
```python
"""Examples:
    read_note("test.md")
    read_note("foo.md", response_format="detailed")
"""
```
Unrealistic paths don't help agent understand real usage.

**✅ Realistic examples:**
```python
"""Examples:
    # Check daily note metadata
    read_note("daily/2025-01-15.md", response_format="minimal")

    # Get project overview before update
    read_note("projects/website-redesign.md", response_format="concise")
"""
```

**❌ No token/performance info:**
```python
"""Returns:
    String containing note content.
"""
```
Agent has no idea about token usage or cost.

**✅ Explicit performance characteristics:**
```python
"""Performance Notes:
    - Minimal format: ~50 tokens (use for metadata checks)
    - Concise format: ~150 tokens (default balance)
    - Detailed format: ~1500+ tokens (only when full content needed)
    - Max file size: 10MB
"""
```

### Writing Process: Think Like an Agent

When writing tool docstrings, ask yourself:

1. **Tool Selection**: "How will the agent know to choose THIS tool vs the 10 other available tools?"
   → Write specific "Use this when" scenarios

2. **Parameter Choices**: "How will the agent know which response_format to use?"
   → Explain token costs and use cases for each option

3. **Error Prevention**: "What mistakes will the agent make if I don't guide it?"
   → Add "Do NOT use" section pointing to correct alternatives

4. **Token Efficiency**: "How can I help the agent minimize token usage?"
   → Document token costs, recommend defaults, show format differences

5. **Composition**: "How does this tool fit into multi-step workflows?"
   → Examples showing tool in context of larger tasks

6. **Edge Cases**: "What will the agent do at boundaries (empty results, max limits)?"
   → Document limits and what happens when exceeded

### Tool Consolidation Principle

When multiple low-level operations can be combined, prefer consolidated tools:

**❌ Fragmented (requires agent to orchestrate):**
```python
read_note(path)      # Tool 1
patch_note(path, old, new)  # Tool 2
update_metadata(path, metadata)  # Tool 3
# Agent must call 3+ tools for simple "update note" task
```

**✅ Consolidated (single tool call):**
```python
obsidian_note_manage(
    path=path,
    operation="patch",  # or "read", "update", "append"
    find_replace=(old, new),
    metadata_updates=metadata
)
# Agent does everything in one call
```

Document the consolidation in tool description:
```python
"""Unified note management - handles read, write, patch, and metadata updates.

This consolidates what would otherwise require 3-4 separate tool calls.
Use operation parameter to specify what you want to do:
- "read": View note content
- "update": Replace entire content
- "patch": Find and replace text
- "append": Add to end of note
"""
```

### Testing Tool Docstrings

**Validate by asking:**

1. **Can an LLM select the right tool?**
   - Give agent a task and 5 tool options
   - Does it pick the right one based on docstrings?

2. **Can an LLM use parameters efficiently?**
   - Does it choose minimal over detailed when appropriate?
   - Does it understand when to use optional parameters?

3. **Does the agent avoid common mistakes?**
   - After reading "Do NOT use", does agent redirect correctly?
   - Does it compose tools properly in multi-step workflows?

**If agent consistently makes mistakes**, the docstring needs improvement, not the agent.

### Key Insight

Even small refinements to tool descriptions can yield dramatic improvements in agent performance. Invest time in tool docstrings—they are the CONTRACT between deterministic tools and non-deterministic agents. Clear contracts → better performance.

---

## Logging Rules

**Philosophy:** Logs are optimized for AI agent consumption. Include enough context for an LLM to understand and fix issues without human intervention.

### Required (MUST)

1. **Import shared logger:** `from src.shared.logging import get_logger; logger = get_logger(__name__)`

2. **Use appropriate levels:** `debug` (diagnostics), `info` (operations), `warning` (recoverable), `error` (non-fatal), `exception` (in except blocks with stack traces)

3. **Use structured logging:** Always use keyword arguments, never string formatting
   ```python
   logger.info("user_created", user_id="123", role="admin")  # ✅
   logger.info(f"User {user_id} created")  # ❌ NO
   ```

4. **Descriptive event names:** Use `snake_case` that answers "what happened?"
   - Good: `database_connection_established`, `tool_execution_started`, `api_request_completed`
   - Bad: `connected`, `done`, `success`

5. **Use logger.exception() in except blocks:** Captures full stack trace automatically
   ```python
   try:
       result = await operation()
   except ValueError:
       logger.exception("operation_failed", expected="int", received=type(value).__name__)
       raise
   ```

6. **Include debugging context:** IDs (user_id, request_id, session_id), input values, expected vs actual, external responses, performance metrics (duration_ms)

### Recommended (SHOULD)

- Log entry/exit for complex operations with relevant metadata
- Log performance metrics for bottlenecks (timing, counts)
- Log state transitions (old_state, new_state)
- Log external system interactions (API calls, database queries, tool executions)
- Use `bind_context()` for request-scoped data (middleware handles this automatically)

### DO NOT

- **DO NOT log sensitive data:** No passwords, API keys, tokens (mask: `api_key[:8] + "..."`)
- **DO NOT use string formatting:** Always use structured kwargs
- **DO NOT spam logs in loops:** Log batch summaries instead
- **DO NOT silently catch exceptions:** Always log with `logger.exception()` or re-raise
- **DO NOT use vague event names:** Be specific about what happened

### Common Patterns

**Tool execution:**
```python
logger.info("tool_execution_started", tool=name, params=params)
try:
    result = await tool.execute(params)
    logger.info("tool_execution_completed", tool=name, duration_ms=duration)
except ToolError:
    logger.exception("tool_execution_failed", tool=name, retry_count=count)
    raise
```

**External API calls:**
```python
logger.info("api_call", provider="openai", endpoint="/v1/chat", status=200,
            duration_ms=1245.5, tokens={"prompt": 245, "completion": 128})
```

### Debugging

Logs include: `correlation_id` (links request logs), `source` (file:function:line), `duration_ms` (performance), `exc_type/exc_message` (errors). Use `grep "correlation_id=abc-123"` to trace requests.

---

## Development Workflow

**Run server:** `uv run uvicorn src.main:app --host 0.0.0.0 --port 8030 --reload`

**Lint/check (must pass):** `uv run ruff check src/ && uv run mypy src/`

**Auto-fix:** `uv run ruff check --fix src/`

**Run tests:** `uv run pytest tests/ -v`

---

## Testing

**Tests mirror the source directory structure.** Every file in `src/` MUST have a corresponding test file.

**Structure:**
```
src/shared/logging.py  →  tests/shared/test_logging.py
src/shared/config.py   →  tests/shared/test_config.py
src/agent/agent.py     →  tests/agent/test_agent.py
```

**Requirements:**
- **Unit tests:** Test individual components in isolation. Mark with `@pytest.mark.unit`
- **Integration tests:** Test multiple components together. Mark with `@pytest.mark.integration`
- Place integration tests in `tests/integration/` when testing full application stack

**Run tests:** `uv run pytest tests/ -v`

**Run specific types:** `uv run pytest tests/ -m unit` or `uv run pytest tests/ -m integration`

---

## Adding Features

1. Create vertical slice in `src/tools/<name>/`
2. Define Pydantic schemas in `schemas.py` (types first)
3. Implement with proper logging, docstrings, and type annotations
4. **Create corresponding test file** in `tests/tools/<name>/test_<module>.py`
5. Write unit tests for the component
6. Add integration tests if the feature interacts with other components
7. Verify linters pass: `uv run ruff check src/ && uv run mypy src/`
8. Ensure all tests pass: `uv run pytest tests/`

---

## AI Agent Notes

When debugging:
- Check `source` field for file/function location
- Use `correlation_id` to trace full request flow
- Look for `duration_ms` to identify bottlenecks
- Exception logs include full stack traces with local variables (dev mode)
- All context is in structured log fields—use them to understand and fix issues
