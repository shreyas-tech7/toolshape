#!/usr/bin/env bash
# Write docs/DEMO.md from a real terminal session. Run from the repo root after ./init.sh.
set -uo pipefail
cd "$(dirname "$0")/.."
TC=.venv/bin/toolcut
run() {
  echo '```console'
  echo "\$ toolcut ${*}"
  timeout 300 "$TC" "$@" 2>&1
  echo "(exit code $?)"
  echo '```'
  echo
}
{
  echo "# Demo"
  echo
  echo "A real terminal session, written by \`scripts/make_demo.sh\` on $(date -u +%Y-%m-%d). Each block shows the exit code. No model and no network."
  echo
  echo "## One task in each shape, over MCP"
  echo
  run demo --task t07
  echo "## A lookup task, where the shapes differ most"
  echo
  run demo --task t33
  echo "## Tool definition sizes"
  echo
  run sizes --out out/demo/tool_sizes.json
  echo "## The oracle and the wrong agents in shape C"
  echo
  run oracle --transport mcp --shapes C --out out/demo/oracle-c.json
  echo "## Replay the scripted agent run from its fixtures"
  echo
  run replay --out out/demo/replay
  echo "## Confirm the README tables"
  echo
  run readme --check
} > docs/DEMO.md
echo "wrote docs/DEMO.md"
