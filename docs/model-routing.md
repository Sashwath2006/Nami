# Model routing (local + cloud)

Hermes has no documented automatic per-task router. It provides the building blocks: a main model, auxiliary slots, `model_aliases`, `fallback_providers`, `/model --once`, and `hermes -p <profile> chat --model <alias>`. `src/nami/core/task_router.py` adds the missing decision step, **before** a session starts (switching mid-session resets the provider prompt cache).

## Decision order

1. **Privacy gate (hard).** Project sensitivity `sensitive` (the default for unregistered projects), or secrets/PII detected in the task text (private keys, AWS/API tokens, credential assignments, emails, SSN-like numbers, Luhn-valid card numbers) => local only. A "use cloud" preference cannot override it; the decision is marked `blocked`.
2. **Master switch.** `allow_cloud: false` => local only.
3. **Locality.** Easy tasks stay local (cheaper, faster, private). `internal` projects require confirmation before cloud.
4. **Strength.** Easy, or voice turns that are not hard => fast tier. Everything else => strong tier.

| Situation | Result |
|---|---|
| Sensitive project, any task | local-strong / local-fast, never cloud |
| Public project, hard refactor | cloud-strong |
| Public project, `git status` | local-fast |
| Internal project, hard task | cloud-strong after confirmation |
| Secret pasted into the prompt | forced local |
| Hard task kept local | warning: weaker results, review carefully |

## Hermes-side setup (per profile)

`nami-local` (no cloud keys at all):

```yaml
model_aliases:
  local-fast:   {model: <small-model>,  provider: custom, base_url: "http://127.0.0.1:11434/v1"}
  local-strong: {model: <larger-model>, provider: custom, base_url: "http://127.0.0.1:11434/v1"}
# Do NOT set fallback_providers here: a failing local model must not silently fall back to cloud.
```

`nami-cloud` (non-sensitive projects only): define `cloud-fast` / `cloud-strong` aliases and keys here. Prefer a paid, no-training tier for anything non-public. Avoid `-contributor` model variants (the vendor may train on prompts).

Auxiliary slots (compression, vision, approval, web extraction) default to `auto` = the main model, so they follow the profile. In `nami-local`, keep any override pointed at a local model.

## Limits

- Heuristic complexity scoring is crude; tune the keyword lists with real usage.
- PII detection is regex-based and will miss names, addresses and free-text personal data. The project classification is the real control.
- The router only picks the model. Files the agent reads during the session are sent to whichever model runs, which is why scope is set per project.
- Not yet wired to a launcher or the project registry; Milestone 2.
