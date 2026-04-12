# Architecture Decision Records

This directory captures the non-obvious architectural choices in the VTV codebase. Each ADR follows the [Nygard template](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):

- **Status** - Accepted, Deprecated, or Superseded by ADR-NNNN
- **Context** - The forces at play, including technical, political, and project-specific constraints
- **Decision** - What we decided and why
- **Consequences** - What becomes easier or harder as a result

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [0001](0001-vertical-slice-architecture.md) | Vertical Slice Architecture | Accepted |
| [0002](0002-pydantic-ai-over-langchain.md) | Pydantic AI over LangChain | Accepted |
| [0003](0003-redis-for-cache-layer.md) | Redis for Cache Layer | Accepted |
| [0004](0004-slowapi-rate-limiting.md) | Application-Level Rate Limiting with slowapi | Accepted |

## Adding a New ADR

1. Copy the template below into `docs/adr/NNNN-short-title.md`
2. Fill in all four sections
3. Add a row to the index table above
4. Update cross-links in `CLAUDE.md` and `README.md` if the decision affects documented architecture

### Template

```
# ADR-NNNN: Title

## Status

Accepted | Deprecated | Superseded by [ADR-NNNN](NNNN-title.md)

## Context

{Problem statement. What forces are at play? What constraints exist?}

## Decision

{What was decided and why. Reference specific alternatives that were considered and rejected.}

## Consequences

{What becomes easier or harder. Both positive and negative outcomes.}
```
