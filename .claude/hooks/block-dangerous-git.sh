#!/bin/bash

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{try{process.stdout.write(JSON.parse(d).tool_input.command||'')}catch(e){}})")

# Anchored to a command boundary (start of line, or after ;/&/|) so the
# pattern only matches an actual invocation, not the phrase appearing in
# prose inside a commit message or file content the command carries as data.
BOUNDARY='(^|[;&|])[[:space:]]*'
DANGEROUS_PATTERNS=(
  "${BOUNDARY}git push"
  "${BOUNDARY}git reset --hard"
  "${BOUNDARY}git clean -fd"
  "${BOUNDARY}git clean -f"
  "${BOUNDARY}git branch -D"
  "${BOUNDARY}git checkout \."
  "${BOUNDARY}git restore \."
)

while IFS= read -r line; do
  for pattern in "${DANGEROUS_PATTERNS[@]}"; do
    if echo "$line" | grep -qE "$pattern"; then
      echo "BLOCKED: '$COMMAND' matches dangerous pattern '$pattern'. The user has prevented you from doing this." >&2
      exit 2
    fi
  done
done <<< "$COMMAND"

exit 0
