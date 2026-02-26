#!/bin/bash
# Filter test/build output to last 60 lines to reduce token consumption.
# Used as a PreToolUse hook for Bash commands.
input=$(cat)
cmd=$(echo "$input" | jq -r '.tool_input.command // empty')

# Only filter known test/build commands
if [[ "$cmd" =~ ^(uv\ run\ pytest|pnpm.*(build|typecheck|lint)) ]]; then
  # Append filter to show only errors + summary
  filtered="$cmd 2>&1 | tail -60"
  echo "{\"hookSpecificOutput\":{\"hookEventName\":\"PreToolUse\",\"permissionDecision\":\"allow\",\"updatedInput\":{\"command\":\"$filtered\"}}}"
else
  echo "{}"
fi
