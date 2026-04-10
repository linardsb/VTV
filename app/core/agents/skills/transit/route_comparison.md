---
name: route_comparison
priority: 3
token_cost: 350
version: 1
keywords: [compare, versus, vs, better, which route, kurs marsruts, salidzinat, atskiriba]
---
# Route comparison

When the user asks to compare two or more routes:

1. Fetch status for each route separately with `query_bus_status` — do not batch mental models across routes.
2. Compare on dimensions the dispatcher actually cares about:
   - Active vehicle count (aktīvie transportlīdzekļi)
   - On-time percentage from `get_adherence_report`
   - Headway (starppieturu laiks) from the schedule tool
3. Present as a compact markdown table with columns per route and rows per metric.
4. Never compare on dimensions you did not fetch. If `get_adherence_report` wasn't called, do not invent an on-time percentage.
5. Finish with a one-sentence recommendation only when the data clearly supports it — otherwise say the routes are comparable.
