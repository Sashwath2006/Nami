# Nami

Local-first personal AI workspace built on [Hermes Agent](https://hermes-agent.nousresearch.com). Hermes provides the agent loop, voice, wake word, approvals, profiles, skills and cron; this repo holds only the gaps: project registry, progress summaries, security tests, and skills.

Status: Phase 0 (baseline). See `docs/phase0-assessment.md`.

Layout: `src/nami` (custom code), `skills/` (Hermes skills), `config/` (example config), `tests/`, `scripts/`, `sandbox-repo/` (throwaway test project, separate git repo).

Decisions: local models only; Hermes Desktop + CLI; wake phrase "hey nami" (sherpa); Docker terminal backend; approvals manual until trusted.
