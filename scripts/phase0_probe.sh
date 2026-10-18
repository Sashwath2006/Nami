#!/usr/bin/env bash
# JARVIS Phase 0 baseline probe. READ-ONLY: installs nothing, changes nothing.
# Secrets: .env is reported by variable NAME only; config.yaml has secret-looking values redacted.
# Usage:  bash scripts/phase0_probe.sh        -> writes docs/phase0-baseline-raw.txt
set +e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$HERE/docs/phase0-baseline-raw.txt"
mkdir -p "$HERE/docs"
HH="${HERMES_HOME:-$HOME/.hermes}"

# macOS has no `timeout`; use perl alarm
to() { local s="$1"; shift; perl -e 'alarm shift; exec @ARGV' "$s" "$@" 2>&1; }
sec() { printf '\n===== %s =====\n' "$1"; }
redact() { sed -E 's/((key|token|secret|password|passwd|credential)[A-Za-z_]*[[:space:]]*[:=][[:space:]]*).+/\1<REDACTED>/I'; }

{
sec "META"; date; echo "whoami: $(whoami)"; echo "shell: $SHELL"; echo "PWD: $PWD"
sec "MACHINE"
sw_vers; uname -m; sysctl -n machdep.cpu.brand_string hw.model 2>/dev/null
echo "RAM bytes: $(sysctl -n hw.memsize)"; echo "perf cores: $(sysctl -n hw.perflevel0.physicalcpu 2>/dev/null)"
df -h "$HOME" | tail -1
sec "TOOLCHAIN"
for t in hermes python3 uv pip3 git brew node npm ffmpeg ollama docker gh sox; do
  p="$(command -v $t 2>/dev/null)"; printf '%-8s %s\n' "$t" "${p:-MISSING}"
done
python3 --version 2>&1; git --version 2>&1; ollama --version 2>&1 | head -2; docker --version 2>&1
echo "brew audio libs:"; brew list --versions portaudio ffmpeg opus espeak-ng 2>&1 | head
sec "HERMES: version / help"
if command -v hermes >/dev/null; then
  to 30 hermes --version
  to 30 hermes --help | head -80
else echo "hermes NOT on PATH"; ls -d "$HH" "$HOME/.local/bin/hermes" /Applications/Hermes* 2>&1; fi
sec "HERMES: home dir (names only)"
ls -la "$HH" 2>&1 | head -60
echo "-- skills dir (count by top-level):"; ls "$HH/skills" 2>/dev/null | wc -l
echo "-- profiles:"; ls "$HH/profiles" 2>&1
sec "HERMES: profile list / doctor / skills / cron / sessions"
to 30 hermes profile list
to 90 hermes doctor
to 30 hermes skills list | head -60
to 30 hermes cron list | head -20
to 30 hermes sessions list | head -10
sec "HERMES: config.yaml (secret-looking values redacted)"
if [ -f "$HH/config.yaml" ]; then redact < "$HH/config.yaml" | head -250; else echo "no config.yaml"; fi
sec "HERMES: .env variable NAMES only"
if [ -f "$HH/.env" ]; then grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$HH/.env" | cut -d= -f1 | sort; else echo "no .env"; fi
sec "HERMES: python env capability check"
HBIN="$(command -v hermes)"; HPY=""
[ -n "$HBIN" ] && HPY="$(head -1 "$HBIN" | sed -n 's/^#!\(.*\)/\1/p' | awk '{print $1}')"
echo "hermes interpreter: ${HPY:-unknown}"
if [ -n "$HPY" ] && [ -x "$HPY" ]; then
  "$HPY" -c '
import importlib.util as u, platform
print("python", platform.python_version(), platform.machine())
for m in ["sounddevice","numpy","faster_whisper","pyopen_wakeword","sherpa_onnx","edge_tts","discord","acp"]:
    print(f"{m:16}", "present" if u.find_spec(m) else "absent")
' 2>&1
fi
sec "VOICE: audio input devices (names only)"
system_profiler SPAudioDataType 2>/dev/null | grep -E '^\s{8}[A-Za-z].*:$|Input Channels|Default Input' | head -20
echo "NOTE: microphone permission for the Hermes backend process cannot be probed non-intrusively."
sec "LOCAL MODELS"
to 10 ollama list
curl -s -m 2 http://127.0.0.1:11434/api/tags >/dev/null && echo "ollama endpoint: UP" || echo "ollama endpoint: down/not installed"
sec "WORKSPACE"
echo "repo root: $HERE"; ls -la "$HERE"
git -C "$HERE" rev-parse --is-inside-work-tree 2>&1
echo "-- candidate git repos under ~/ (depth<=3, names only):"
find "$HOME" -maxdepth 3 -name .git -type d -not -path '*/Library/*' -not -path '*/.hermes/*' -not -path '*/node_modules/*' 2>/dev/null | sed 's#/.git$##' | head -20
sec "DONE"
} > "$OUT" 2>&1

echo "Wrote $OUT"
echo "Review it for anything you consider private, then tell Claude it's ready."
