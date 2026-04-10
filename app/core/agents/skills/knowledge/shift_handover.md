---
name: shift_handover
priority: 3
token_cost: 300
version: 1
keywords: [handover, nodosana, shift report, mainas, nodot, takeover, prieksnieks]
---
# Shift handover

When the user asks about shift handover notes, previous shift status, or operational continuity:

1. Call `search_knowledge_base` with terms from the shift date and dispatcher name if provided.
2. Summarize in three sections: open incidents, resolved items, follow-ups for the next shift.
3. Do NOT merge handover notes from different shifts unless the user explicitly asks for a range.
4. When no handover exists for the requested shift, say so ("nav nodošanas piezīmju"). Do not invent one.
5. Cite each handover note with its document link. If multiple notes apply, list each separately — do not concatenate.
