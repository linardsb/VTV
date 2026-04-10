---
name: bulk_operations
priority: 3
token_cost: 250
version: 1
keywords: [bulk, rename, move, parvietot, parsaukt, delete, dzest, mass, daudz, batch]
---
# Vault bulk operations

When the user asks for a batch rename, move, or delete across multiple notes:

1. ALWAYS call `obsidian_bulk_operations` with `dry_run=true` on the FIRST call. Show the preview to the user before anything is written.
2. Ask for explicit confirmation ("Confirm? / Apstiprināt?") BEFORE re-running with `dry_run=false`.
3. For destructive ops (delete, rename-over-existing), summarize the count and list the first 10 affected paths so the user can spot mistakes.
4. Never chain a bulk operation with another tool call in the same turn — the user must be able to stop between preview and execution.
5. After execution, report what actually changed (from the tool result), not what the preview said.
