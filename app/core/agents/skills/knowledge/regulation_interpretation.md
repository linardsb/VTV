---
name: regulation_interpretation
priority: 2
token_cost: 450
version: 1
keywords: [regulation, law, likums, noteikumi, compliance, atbilstiba, eu, es, directive, direktiva, rules]
---
# Regulation interpretation

When the user asks about regulations, laws, or compliance requirements:

1. Call `search_knowledge_base` with a query that includes the regulation name/number (e.g. "EU 561/2006 driving hours"). Do not paraphrase from prior knowledge.
2. Quote the regulation text verbatim when it answers the question; paraphrase only when synthesising across multiple sections.
3. Always include the document title + article/section number in the citation.
4. If the user asks a yes/no compliance question, answer yes/no FIRST, then explain the reasoning with cited clauses.
5. When the knowledge base lacks the regulation, say so clearly ("nav informācijas par [regulation]") — do not fall back to memorised legal knowledge.
6. Flag effective dates: if a regulation has a future start date or was amended, mention it explicitly.
