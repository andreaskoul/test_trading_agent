#!/usr/bin/env bash
# Installs the local scheduler: ~/.fund-runner (runner, venv, secrets template) and a launchd agent
# that runs `runner.py tick` every minute. Re-run after changing fund/local/ or requirements.txt.
# The schedule starts DISABLED: fill ~/.fund-runner/secrets.env, turn off the cron-job.org jobs,
# then `~/.fund-runner/venv/bin/python ~/.fund-runner/runner.py enable`.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
H="$HOME/.fund-runner"; label=com.andreaskoul.fund-runner
plist="$HOME/Library/LaunchAgents/$label.plist"
mkdir -p "$H" "$HOME/Library/Logs/fund"
# a native Python 3.11 (as CI): an Intel (Rosetta) Python finds no llvmlite wheel for umap-learn on Apple silicon
uv=$(command -v uv || ls "$HOME"/.langflow/uv/uv "$HOME"/.local/bin/uv "$HOME"/.cargo/bin/uv 2>/dev/null | head -1 || true)
py="${FUND_PYTHON:-}"
if [ -z "$py" ] && [ -n "$uv" ]; then "$uv" python install -q 3.11 && py=$("$uv" python find 3.11); fi
py="${py:-$(command -v python3.11 || command -v python3)}"
if [ "$(uname -m)" = arm64 ] && ! file "$py" | grep -q arm64; then
  echo "$py is not a native arm64 build; install uv (https://docs.astral.sh/uv/) or set FUND_PYTHON" >&2; exit 1
fi
if [ -x "$H/venv/bin/python" ] && ! file -L "$H/venv/bin/python" | grep -q "$(uname -m)"; then rm -rf "$H/venv"; fi
[ -x "$H/venv/bin/python" ] || "$py" -m venv "$H/venv"
"$H/venv/bin/pip" install -q --upgrade pip
"$H/venv/bin/pip" install -q -r "$here/../../requirements.txt"
cp "$here/runner.py" "$H/runner.py"
if [ ! -f "$H/secrets.env" ]; then cp "$here/secrets.env.example" "$H/secrets.env"; echo "created $H/secrets.env: fill it in"; fi
chmod 600 "$H/secrets.env"
[ -f "$H/state.json" ] || "$H/venv/bin/python" "$H/runner.py" tick --init     # nothing fires for slots already past
cat > "$plist" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>$label</string>
  <key>ProgramArguments</key><array><string>$H/venv/bin/python</string><string>$H/runner.py</string><string>tick</string></array>
  <key>StartInterval</key><integer>60</integer>
  <key>RunAtLoad</key><true/>
  <key>SoftResourceLimits</key><dict><key>NumberOfFiles</key><integer>24576</integer></dict>
  <key>HardResourceLimits</key><dict><key>NumberOfFiles</key><integer>24576</integer></dict>
  <key>StandardOutPath</key><string>$HOME/Library/Logs/fund/scheduler.log</string>
  <key>StandardErrorPath</key><string>$HOME/Library/Logs/fund/scheduler.log</string>
  <key>EnvironmentVariables</key><dict><key>PATH</key><string>/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin</string></dict>
</dict></plist>
PL
launchctl bootout "gui/$(id -u)/$label" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$plist"
echo "launchd agent $label loaded"
"$H/venv/bin/python" "$H/runner.py" status
