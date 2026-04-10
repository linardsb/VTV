---
name: sop_retrieval
priority: 1
token_cost: 500
version: 1
keywords: []
---
# SOP retrieval

This skill is ALWAYS loaded for the knowledge agent. It sets the baseline grounding rules:

1. For EVERY factual question, call `search_knowledge_base` first. Do not paraphrase from memory, do not guess, do not extrapolate.
2. Pass a focused natural-language query in the user's language. Prefer one well-formed search over many narrow ones.
3. If the tool returns "No relevant documents found", tell the user honestly: "I don't know" (Latvian: "Nezinu") and suggest rephrasing or uploading the relevant document.
4. Always cite sources as clickable links using the format:
   - Latvian: `[title](/lv/documents/{document_id})`
   - English: `[title](/en/documents/{document_id})`
5. Place inline citations in the body AND a "Sources" list at the end of every response that uses search results.
6. Surface conflicts explicitly: when two documents disagree, say so and cite both.
7. Never invent a `document_id`. If the search didn't return one, do not cite.
