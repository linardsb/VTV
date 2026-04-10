---
name: driver_availability
priority: 3
token_cost: 300
version: 1
keywords: [driver, vaditajs, staffing, available, briva, brivie, shift, mains]
---
# Driver availability

When the user asks about driver staffing, availability, or shifts:

1. Call `check_driver_availability` first with the exact shift window (start + end) the dispatcher specified.
2. Present the result as a short summary: total available, total assigned, any gaps. Use a table only when there are more than 5 rows.
3. Do NOT include personally identifying information beyond what the tool already returned. Never infer identity from partial data.
4. If the user asks about a specific driver, call the tool with the full name — do not filter in your head.
5. When no drivers match, say so explicitly ("nav pieejamu vadītāju"); do not suggest alternative shifts unless asked.
