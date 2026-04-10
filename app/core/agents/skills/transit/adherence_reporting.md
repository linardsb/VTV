---
name: adherence_reporting
priority: 3
token_cost: 350
version: 1
keywords: [adherence, on-time, performance, report, atskaite, ipasibas, snieguma, statistika]
---
# Adherence reporting

When the user asks for on-time performance or an adherence report:

1. Call `get_adherence_report` with an explicit window (start_time, end_time). Never default silently.
2. Report the three core metrics:
   - On-time percentage (kavēšanās % zem 5 minūtēm)
   - Average deviation in minutes (vidējā novirze)
   - Worst offender (sliktākais reiss) with route + time
3. Use a short markdown table for multi-route comparisons; a sentence for single-route queries.
4. If the tool returns an empty window, state "nav datu par periodu" — never extrapolate.
5. Flag stale data: if the newest record is older than 2 hours, note that explicitly.
6. Do not claim trends without at least 3 data points.
