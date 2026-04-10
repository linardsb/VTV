---
name: incident_response
priority: 2
token_cost: 400
version: 1
keywords: [incident, emergency, avarija, negadijums, response, procedure, procedura, reaction, reakcija]
---
# Incident response

When the user asks about how to respond to an incident or emergency:

1. Call `search_knowledge_base` with the incident type and any keyword the user supplied (accident, fire, medical, etc.).
2. Return the procedure as a numbered list in the order the knowledge base presents it. Do NOT reorder steps.
3. Lead with the immediate life-safety steps if the knowledge base has them — even if the user asked about paperwork.
4. Always include the contact numbers / escalation path from the cited procedure. Do not paraphrase phone numbers.
5. If the procedure depends on jurisdiction or location, surface the condition ("if in Riga city limits..."); do not assume.
6. End with the citation to the authoritative procedure document.
