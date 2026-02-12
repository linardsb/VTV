---
description: Load AI agent tool designs, patterns, and architecture context
argument-hint:
allowed-tools: Read, Glob, Grep
---

This command is a specialized context loader for AI agent tool development. While `/prime` gives you the full project picture, `/prime-tools` dives deep into the agent tool system: it reads tool specifications from `mvp-tool-designs.md`, the PRD's agent sections, and CLAUDE.md's tool docstring standards. It then inventories which tools are implemented vs. planned, checks existing docstrings against the agent-optimized format, and reviews dry-run patterns and error response formats.

The output is a tool-focused summary: a complete tool inventory table (name, status, type, dry-run support, composition chains), design pattern assessment (docstring format, error handling, token efficiency, response structure), and workflow chains showing how tools compose into multi-step agent operations. This is everything you need to know before building or modifying an agent tool.

Use this before running `/planning` for a tool feature, when debugging agent tool behavior, or when reviewing whether existing tools follow VTV's agent-optimized patterns. The 5-principle docstring standard (selection guidance, token waste prevention, composition hints, expectations, examples) is critical for tools because their docstrings are read by LLMs during tool selection, not by human developers.

# Prime Tools — Load AI Agent Tool Context

> **This is tool priming for AI agent development.** Tools are functions that an LLM calls during autonomous workflows. Everything here is optimized for machine consumption — docstrings guide tool selection, responses minimize tokens, errors are actionable.

## INPUT

You are priming yourself with a complete understanding of VTV's agent tool system. Read everything before producing output.

## PROCESS

### 1. Read tool specifications

Load these files directly into context:

@mvp-tool-designs.md
@PRD.md
@CLAUDE.md

Focus on:
- `mvp-tool-designs.md` — consolidated tool designs (the source of truth)
- `PRD.md` — sections on AI agent, Obsidian integration, transit data
- `CLAUDE.md` — "Tool Docstrings for Agents" section for docstring standards

### 2. Understand the agent architecture

From PRD and tool designs, identify:
- What the unified AI agent does (transit CMS + Obsidian integration)
- How tools compose into multi-step workflows
- Which tools are read-only vs. have side effects
- Which tools support dry-run mode
- Token budget constraints and efficiency patterns

### 3. Inventory existing tool implementations

- Search `app/` for any implemented tool modules (service files with tool functions)
- Check for tool registration patterns (how tools are exposed to the agent)
- Identify which tools from `mvp-tool-designs.md` are implemented vs. planned

### 4. Review tool patterns in codebase

- Check existing tool docstrings — do they follow agent-optimized format?
- Look for dry-run parameter patterns
- Check error response formats (are they LLM-actionable?)
- Review structured logging for tool execution events (`agent.tool.*`)

### 5. Check related infrastructure

- Database models that tools interact with
- External service integrations (Obsidian vault paths, transit APIs)
- Configuration for tool-related settings in `app/core/config.py`

## OUTPUT

Present a scannable summary using this structure:

**Agent System:** VTV — [one-line description of agent purpose from PRD]

**Tool Architecture:**
- Total tools designed: [count from mvp-tool-designs.md]
- Tools implemented: [count and names]
- Tools planned: [count and names]
- Dry-run capable: [which tools]

**Tool Inventory:**

| Tool | Status | Type | Dry-Run | Composition |
|------|--------|------|---------|-------------|
| [name] | implemented/planned | read/write | yes/no | [what it chains with] |

**Tool Design Patterns:**
- Docstring format: [agent-optimized 5-element or standard]
- Error handling: [LLM-actionable or generic]
- Token efficiency: [strategies used]
- Response format: [structured/unstructured]

**Agent Workflow Chains:**
- [Chain 1]: tool_a → tool_b → tool_c — [purpose]
- [Chain 2]: tool_x → tool_y — [purpose]

**Docstring Standard (from CLAUDE.md):**
1. Guide tool selection — when to use, when NOT to use
2. Prevent token waste — efficient parameter choices
3. Enable composition — what tools to chain before/after
4. Set expectations — performance characteristics and limits
5. Provide examples — concrete usage with realistic data

**Key Files:**
- Tool designs: `mvp-tool-designs.md`
- Agent config: [path if exists]
- Tool modules: [paths of implemented tools]

**Next Steps:**
- [What tools should be built next based on PRD priority]
- [Any gaps between designs and implementation]
