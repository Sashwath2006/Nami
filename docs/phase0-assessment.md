# JARVIS Phase 0: Baseline Assessment (interim)

Status: **docs-verified, installed-version unverified.** My sandbox is Linux and cannot see your Mac or `~/.hermes`. Run `bash scripts/phase0_probe.sh` and I will confirm every "docs" row below against your installed version.

## 1. Baseline

| Item | Finding | Evidence |
|---|---|---|
| Workspace `/Users/sashwath/Nami` | Empty, not a git repo | Verified |
| Hermes installed / version | Unknown | Needs probe |
| Provider configured | Unknown | Needs probe |
| Mac audio / mic / Python / Ollama | Unknown | Needs probe |
| Official docs | Reachable and read: quickstart, profiles, voice mode, wake word, security | Verified |

## 2. Capability matrix (from official docs; confirm on installed version)

| Capability | Status | Detail |
|---|---|---|
| Agent loop, sessions, `--continue` resume | Built-in | `hermes sessions list`, `hermes -c` |
| Push-to-talk, STT, streaming TTS, barge-in, "stop" phrase | Built-in | `/voice on`, Ctrl+B; local faster-whisper (no key), Edge TTS (no key) |
| Wake word | Built-in | On-device openWakeWord ("hey hermes" bundled) or sherpa (any typed phrase); off by default; Apple Silicon supported (macOS 15+ for openWakeWord wheel) |
| Wake word "jarvis" | Configurable | `provider: sherpa`, `phrase: "hey jarvis"` (no key); Porcupine's default keyword is "jarvis" but needs an Picovoice key |
| Mic mute / visible state | **Gap** | Docs show `/wake off` and a desktop ear toggle; no hardware-mute integration documented |
| Approvals (smart/manual/off) | Built-in | `approvals.mode`; fail-closed timeout |
| Hardline blocklist, user deny globs | Built-in / Configurable | `approvals.deny` (e.g. `git push --force*`). Docs state it is a command-pattern policy, not a sandbox |
| File-write sandbox | Configurable | `HERMES_WRITE_SAFE_ROOT`; secret paths and project `.env` read-denied |
| Real isolation | Configurable | `terminal.backend: docker`. Default `local` has no isolation; profiles are **not** sandboxes |
| Profiles (separate memory/config/keys/skills/cron) | Built-in | `hermes profile create`, `-p`; one process per profile home |
| Skills (`SKILL.md`, slash commands, hub) | Built-in | `~/.hermes/skills/`; external skill dirs: **verify exact config key** |
| Cron / scheduled tasks | Built-in | `hermes cron`; headless danger prompts denied by default |
| Local model (Ollama/LM Studio/custom endpoint) | Configurable | Hard requirement: model context **≥ 64K** |
| Checkpoints / rollback, git worktrees | Built-in (per docs nav) | Verify behaviour; I have not read these pages |
| Subagents (`delegate_task`) | Built-in (per docs) | Verify; not yet read |
| Spotify, browser, computer-use | Built-in (per docs nav) | Phase 7; verify |
| Project registry + per-project summaries | **Custom** | Thin: a YAML file plus skill |
| Progress-summary + resume-with-fresh-state check | **Custom** (skill) | Skill that re-inspects git before trusting old state |
| Audit log of tool actions | **Verify, likely partial** | Session history exists; need to check for a dedicated action log |
| Test/permission enforcement tests | **Custom** | `tests/security` |
| Desktop dashboard | Built-in alternative | Hermes Desktop / web dashboard exist; Phase 6 may be unnecessary |

## 3. Proposed minimal architecture

Spec items 6, 10 and most of 4 and 9 are already Hermes features, so building them would violate your "do not duplicate" rule. Proposed:

```
Hermes Agent (CLI/TUI, later Desktop)   <- voice, wake word, sessions, approvals, cron, memory
  profile: jarvis        (config.yaml + SOUL.md persona + approvals.deny + terminal.cwd)
  skills/ (in repo, linked into Hermes skill path)
  jarvis/ (small Python package, only real gaps)
     projects.py   registry (YAML) + secret-path exclusions
     summary.py    progress summary + resume freshness check (git-verified)
     audit.py      redacted JSONL action log, only if Hermes lacks one
  tests/ (unit + security: deny rules, redaction, cross-project isolation)
Optional later: profile jarvis-sec (isolated creds/permissions) for security audits
```

Deliberately not built: custom orchestrator, router, session manager, voice stack, permission engine, dashboard.

## 4. Prioritised backlog

1. P0: Run probe; confirm Hermes version, provider, `hermes doctor`, text chat works.
2. P1: Create `jarvis` profile with SOUL.md, `approvals.mode: manual` (until trust built), `approvals.deny` list, `terminal.cwd`.
3. P1: Repo scaffold (git init, `.gitignore` excluding `.env`/secrets, README, config.example).
4. P1: `project-recon` skill + project registry; run on a throwaway test repo.
5. P2: `git-workflow`, `feature-implementation`, `debugging`, `code-review` skills.
6. P2: `session-resume` skill + summary generator with freshness check.
7. P2: Voice push-to-talk via `/voice on`; measure latency/CPU.
8. P3: Wake word (sherpa "hey jarvis"), false-trigger tuning, mute procedure.
9. P3: Docker terminal backend for security-audit profile.
10. P4: security-audit, technical-research, report-generation skills; cron workflows.
11. P4: Integrations (Spotify, browser) and dashboard decision.

## 5. Milestone 1: "Verified baseline + first safe vertical slice"

Objective: JARVIS profile answers by text, registers one throwaway repo, runs project-recon, and a blocked command stays blocked.

Acceptance tests:

1. `hermes --version` and `hermes doctor` pass; one plain chat turn succeeds on the configured provider.
2. `hermes -p jarvis` starts with its own config and memory (verify via `hermes profile show jarvis`).
3. `approvals.deny` blocks `git push --force origin main` in a live session (command not executed; BLOCKED shown).
4. Reading a project `.env` is refused by the file tool.
5. `project-recon` on a test repo produces a summary whose language, test command and git status match manual inspection.
6. `hermes -c` resumes the session after restart.
7. Automated: `pytest tests/` passes for registry and redaction units.

## 6. Decisions needed

1. **Provider/privacy:** which provider(s) may see your source code (Nous Portal, Anthropic, OpenRouter, local Ollama only)? Default stance: nothing leaves the machine until you name one.
2. **Install shape:** Hermes Desktop app, CLI install, or both? Affects where skills load and how wake word runs.
3. **Wake phrase and engine:** "hey jarvis" via sherpa (free, keyless, my recommendation) vs "hey hermes" via openWakeWord (bundled model).
4. **Isolation level for coding:** local backend with approvals and deny rules (fast to start, no true sandbox) vs Docker backend from day one (stronger, more setup and slower on a MacBook Air).
5. **Test repo:** point me at a small throwaway repo, or let me create one in `Nami/sandbox-repo`.
6. **Approval to proceed:** OK to `git init` this folder and scaffold the repo structure above?

## Risks

- Docs describe the latest release; your installed version may differ, so features are unconfirmed until probed.
- Default local backend gives the agent your full user permissions; approvals are pattern-based and bypassable by indirection (docs say so).
- Local models must have ≥64K context, which is memory-heavy on a MacBook Air; cloud is likely better for coding quality at first.
- macOS grants mic permission per process; the wake listener runs in the Python backend and needs its own grant.
- Always-on wake detection costs idle CPU; must be measured, not assumed.
