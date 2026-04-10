---
name: delay_analysis
priority: 2
token_cost: 450
version: 1
keywords: [delay, late, behind, on time, schedule, adherence, kavesanas, kavejas, nokavejies, kavejums, kave]
---
# Delay analysis

When the user asks about delays or schedule adherence:

1. Always call `get_adherence_report` first — never estimate from memory or guess from partial tool context.
2. Distinguish trip-level (single run/reiss) from route-level (rolling window over many trips). Ask which one the dispatcher needs if unclear.
3. Magnitude buckets for reporting:
   - Under 2 minutes: on time (laikā)
   - 2-5 minutes: minor delay (neliels kavējums)
   - 5-15 minutes: significant delay (ievērojams kavējums)
   - Over 15 minutes: critical delay (kritisks kavējums)
4. If the timeframe is missing, ask — do NOT silently fall back to "today" or "now".
5. When hypothesising a root cause, only do so when the tool data explicitly supports it (e.g. terminal departure times, vehicle counts). Never speculate.
6. Report in the user's language (Latvian by default) with Latvian diacritics.
