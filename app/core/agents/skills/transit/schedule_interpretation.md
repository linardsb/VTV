---
name: schedule_interpretation
priority: 2
token_cost: 400
version: 1
keywords: [schedule, timetable, grafiks, saraksts, departure, arrival, atiesana, ienaksana, reiss, trip]
---
# Schedule interpretation

When the user asks for timetables or scheduled departures:

1. Call `get_route_schedule` with an explicit `service_date` — never assume "today" unless the user said so.
2. If the user names a stop instead of a route, call `search_stops` first to resolve the stop, then use the matching route on `get_route_schedule`.
3. When presenting times, use 24-hour HH:MM in the user's locale. Group by direction (virziens) when both directions exist.
4. Headways (starppieturu laiks) should be computed from consecutive scheduled departures, not estimated.
5. If the schedule returned is empty, state clearly "no trips scheduled" (nav plānotu reisu) rather than guessing.
6. Never fabricate a route number or a stop name — if the tool result doesn't contain it, say you don't know.
