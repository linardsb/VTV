# Plan: Improve Latvian Language Quality for AI Agent

**Created:** 2026-02-19
**Scope:** Backend (system prompt) + Frontend (i18n fixes)
**Risk:** Low — text changes only, no logic changes

---

## Problem Analysis

The AI agent's Latvian output is poor. Evidence from screenshot:

1. **Agent misunderstood "Kuri marsruti sodiena kave?"** — interpreted "kave" as "kāve" (coffee) instead of understanding the user meant "kavējas" (are delayed). Root cause: system prompt is 100% English, agent has no Latvian transit terminology context.
2. **"Papildinformation:"** — incorrect Latvian word. Should be "Papildinformācija:". The agent generates broken Latvian because it has no language guidance.
3. **Frontend text missing diacritics** — "AI paligs" should be "AI palīgs", "Jautajiet" → "Jautājiet", etc. The `chat` namespace in `lv.json` has all diacritics stripped (the rest of the file is correct).
4. **Tool output strings are English** — "on time", "3 min late", "No active vehicles found" — the LLM must translate these on-the-fly without guidance.

## Root Causes

| Issue | Root Cause | Fix Location |
|-------|-----------|--------------|
| Agent responds in broken Latvian | System prompt is 100% English | `app/core/agents/agent.py` |
| Agent misunderstands Latvian input | No Latvian transit glossary in prompt | `app/core/agents/agent.py` |
| UI text missing diacritics | `chat` keys in lv.json have ASCII-only text | `cms/apps/web/messages/lv.json` |
| Suggestion chips send broken Latvian | Suggestion text is wrong Latvian | `cms/apps/web/messages/lv.json` |

## Solution: Two Changes

### Change 1: Rewrite System Prompt (Backend) — HIGH IMPACT

**File:** `app/core/agents/agent.py` — `SYSTEM_PROMPT` constant

**Strategy:** Add Latvian language instructions, transit terminology glossary, and behavioral rules. Keep tool docstrings in English (they're for the LLM's reasoning, not user-facing).

**New system prompt design:**

```
LANGUAGE RULES:
- ALWAYS respond in Latvian (latviešu valoda)
- Use proper Latvian diacritics: ā, č, ē, ģ, ī, ķ, ļ, ņ, š, ū, ž
- If user writes in English, respond in English
- Match the user's language

LATVIAN TRANSIT GLOSSARY (use these terms):
- maršruts = route
- pietura = stop
- grafiks = schedule/timetable
- kavēšanās/kavējas = delay/delayed
- laikā = on time
- agrāk = early
- vēlāk = late
- transportlīdzeklis/autobuss = vehicle/bus
- vadītājs = driver
- reiss = trip
- virziens = direction
- bāzes pieturas = terminal stops
- starppieturu laiks = headway

RESPONSE STYLE:
- Be direct and actionable — dispatchers need quick answers
- When user asks about delays, immediately call tools and report results
- Don't ask clarifying questions unless genuinely ambiguous
- Format transit data as clean markdown tables
- Translate tool output to Latvian (tool returns English data)
```

**Why this works:** The LLM already synthesizes tool output into natural language (per existing RESPONSE FORMAT RULES). Adding language instructions means it synthesizes into Latvian instead of English. Tool outputs stay in English (no test breakage, no logic changes).

**Why NOT change tool outputs:** Tool return values are intermediate data consumed by the LLM, never shown to users. Changing them to Latvian would:
- Break 104+ transit tests that assert English strings
- Make tool output less useful for English-speaking models
- Add complexity with zero user-visible benefit (LLM translates anyway)

### Change 2: Fix Frontend i18n Diacritics — MEDIUM IMPACT

**File:** `cms/apps/web/messages/lv.json` — `chat` namespace (lines 198-217)

**Current (broken):**
```json
"chat": {
  "title": "AI paligs",
  "placeholder": "Jautajiet par marsrutiem, grafikiem, transportlidzekliem...",
  "send": "Nosutit",
  "clear": "Notirit sarunu",
  "thinking": "Domaju...",
  "error": "Radas kluda. Ludzu, meginiet velreiz.",
  "rateLimitError": "Vaicajumu limits sasniegts. Meginiet velreiz velak.",
  "emptyTitle": "Ka es varu palidzet?",
  "emptyDescription": "Jautajiet par autobusu marsrutiem, kavesanos, vaditaju grafikiem vai transporta operacijam.",
  "suggestion1": "Kuri marsruti sodiena kave?",
  "suggestion2": "Paradiet 22. marsruta grafiku",
  "suggestion3": "Cik autobusu ir aktivie?",
  "suggestion4": "Atrast pieturas netalu no centra",
  "you": "Jus",
  "assistant": "VTV asistents",
  "retry": "Meginat velreiz",
  "copied": "Nokopets",
  "copy": "Kopet"
}
```

**Fixed (proper Latvian):**
```json
"chat": {
  "title": "AI palīgs",
  "placeholder": "Jautājiet par maršrutiem, grafikiem, transportlīdzekļiem...",
  "send": "Nosūtīt",
  "clear": "Notīrīt sarunu",
  "thinking": "Domāju...",
  "error": "Radās kļūda. Lūdzu, mēģiniet vēlreiz.",
  "rateLimitError": "Vaicājumu limits sasniegts. Mēģiniet vēlreiz vēlāk.",
  "emptyTitle": "Kā es varu palīdzēt?",
  "emptyDescription": "Jautājiet par autobusu maršrutiem, kavēšanos, vadītāju grafikiem vai transporta operācijām.",
  "suggestion1": "Kuri maršruti šodien kavējas?",
  "suggestion2": "Parādiet 22. maršruta grafiku",
  "suggestion3": "Cik autobusu šobrīd ir aktīvi?",
  "suggestion4": "Atrast pieturas netālu no centra",
  "you": "Jūs",
  "assistant": "VTV asistents",
  "retry": "Mēģināt vēlreiz",
  "copied": "Nokopēts",
  "copy": "Kopēt"
}
```

**Key fixes:**
- All diacritics restored (ā, ē, ī, ū, š, ž, ļ, ņ, ķ, ģ, č)
- `suggestion1`: "Kuri marsruti sodiena kave?" → "Kuri maršruti šodien kavējas?" (correct grammar — the original was nonsensical and caused the "coffee" misunderstanding)
- `suggestion3`: "Cik autobusu ir aktivie?" → "Cik autobusu šobrīd ir aktīvi?" (correct adjective form)

---

## Implementation Steps

### Step 1: Update system prompt in agent.py
- Edit `SYSTEM_PROMPT` in `app/core/agents/agent.py`
- Add Latvian language rules, transit glossary, behavioral guidelines
- Keep existing RESPONSE FORMAT RULES (they're good)
- No test changes needed (tests use TestModel, don't check prompt text)

### Step 2: Fix i18n diacritics in lv.json
- Edit `cms/apps/web/messages/lv.json` chat namespace
- Replace all 17 keys with properly diacritized Latvian
- Fix suggestion1 grammar ("kave" → "kavējas")

### Step 3: Fix hardcoded English fallback in use-chat-agent.ts
- Line 47: `"No response received."` → use i18n or Latvian-safe fallback
- Line 101: same pattern in `retryLast`

### Step 4: Validate
- Backend: `uv run mypy app/ && uv run pyright app/ && uv run pytest -v -m "not integration"`
- Frontend: `cd cms && pnpm --filter @vtv/web type-check && pnpm --filter @vtv/web lint`
- Manual: Send "Kuri maršruti šodien kavējas?" via chat UI and verify Latvian response

---

## What We're NOT Changing (and why)

| Not changing | Reason |
|---|---|
| Tool output strings ("on time", "3 min late") | LLM translates these; changing breaks 104+ tests |
| Tool docstrings language | LLM reasoning works best in English; only user-facing output needs Latvian |
| Error messages in tool return values | LLM synthesizes these; never shown raw to user |
| en.json | English translations are correct |

## Files Modified

| File | Change |
|------|--------|
| `app/core/agents/agent.py` | Rewrite SYSTEM_PROMPT with Latvian instructions |
| `cms/apps/web/messages/lv.json` | Fix chat namespace diacritics + grammar |
| `cms/apps/web/src/hooks/use-chat-agent.ts` | Fix hardcoded English fallback string |
