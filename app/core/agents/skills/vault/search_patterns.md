---
name: search_patterns
priority: 2
token_cost: 300
version: 1
keywords: [search, find, meklet, atrast, where, kur, note, piezime, tag, birka]
---
# Vault search patterns

When the user asks to find notes in the Obsidian vault:

1. Call `obsidian_query_vault` FIRST. Do not guess paths.
2. Prefer the most specific lookup mode available:
   - By tag (`tags: [driver-ops]`) when the user mentions a category
   - By glob (`patterns/**/*.md`) when the user knows the folder
   - By text search when the user quotes phrasing from inside the note
3. Present results as a numbered list with title + relative path. Limit to the top 10 unless the user asked for more.
4. If the search returns zero results, say so explicitly and suggest alternative queries (different tag, broader text).
5. Never open or edit a note until the user confirms which result they want.
