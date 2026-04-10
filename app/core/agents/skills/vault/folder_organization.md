---
name: folder_organization
priority: 3
token_cost: 250
version: 1
keywords: [folder, mape, organize, strukturet, hierarchy, hierarhija, tree, koks]
---
# Vault folder organization

When the user asks about folder structure or organization:

1. Use `obsidian_query_vault` with a glob pattern to inspect the current tree before suggesting changes.
2. Use `obsidian_manage_folders` for create/rename/delete at folder level — never move notes individually when a folder op would do it.
3. For folder deletion, ALWAYS pass `confirm=true` only after the user has explicitly agreed in the current turn. Show what will be removed first.
4. Propose an organization scheme only when the user asks for it; otherwise report the current state faithfully.
5. Never collapse folders that contain notes the user hasn't reviewed — surface a warning and ask.
