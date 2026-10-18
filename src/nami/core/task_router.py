"""Deterministic local/cloud model router.

Privacy is a hard gate, not a score: sensitive data can never route to a cloud tier.
Rules are plain code so every decision is explainable, testable and free (no LLM call).
The router runs BEFORE a Hermes session starts, because switching models mid-session
resets the provider prompt cache (per Hermes docs).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, IntEnum


class Sensitivity(IntEnum):
    PUBLIC = 0      # open-source / throwaway code, no personal data
    INTERNAL = 1    # private but not personal; cloud only with confirmation
    SENSITIVE = 2   # personal data, credentials, third-party data: local only


class Complexity(IntEnum):
    EASY = 0
    MEDIUM = 1
    HARD = 2


class Tier(str, Enum):
    LOCAL_FAST = "local_fast"
    LOCAL_STRONG = "local_strong"
    CLOUD_FAST = "cloud_fast"
    CLOUD_STRONG = "cloud_strong"

    @property
    def is_cloud(self) -> bool:
        return self in (Tier.CLOUD_FAST, Tier.CLOUD_STRONG)


@dataclass(frozen=True)
class RouterConfig:
    allow_cloud: bool = False
    cloud_confirm_internal: bool = True
    local_profile: str = "nami-local"
    cloud_profile: str = "nami-cloud"
    # Hermes model_aliases names (defined in the profile's config.yaml)
    aliases: dict = field(default_factory=lambda: {
        Tier.LOCAL_FAST: "local-fast",
        Tier.LOCAL_STRONG: "local-strong",
        Tier.CLOUD_FAST: "cloud-fast",
        Tier.CLOUD_STRONG: "cloud-strong",
    })
    local_context_limit: int = 64_000   # Hermes minimum; set to your local model's real window
    treat_pii_as_sensitive: bool = True


@dataclass(frozen=True)
class Decision:
    tier: Tier
    profile: str
    alias: str
    complexity: Complexity
    reasons: tuple
    needs_confirmation: bool = False
    warnings: tuple = ()
    blocked: bool = False

    def hermes_command(self) -> list[str]:
        """Argv to start a session with the chosen profile and model alias (flags per Hermes docs)."""
        return ["hermes", "-p", self.profile, "chat", "--model", self.alias]

    def log_record(self) -> dict:
        """Audit-safe record: never includes the task text."""
        return {"tier": self.tier.value, "profile": self.profile, "alias": self.alias,
                "complexity": self.complexity.name, "reasons": list(self.reasons),
                "needs_confirmation": self.needs_confirmation, "blocked": self.blocked}


# ---- detection ---------------------------------------------------------------------------

_SECRET_PATTERNS = [
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("AWS access key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("API token", re.compile(r"\b(sk|pk|ghp|gho|xox[abp])[-_][A-Za-z0-9_-]{16,}\b")),
    ("credential assignment", re.compile(
        r"(?i)\b(api[_-]?key|secret|password|passwd|token)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}")),
]
_PII_PATTERNS = [
    ("email address", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("SSN-like number", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
]
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
        alt = not alt
    return total % 10 == 0


def detect_sensitive(text: str, include_pii: bool = True) -> list[str]:
    found = [name for name, rx in _SECRET_PATTERNS if rx.search(text)]
    if include_pii:
        found += [name for name, rx in _PII_PATTERNS if rx.search(text)]
        for m in _CARD.finditer(text):
            digits = re.sub(r"\D", "", m.group())
            if 13 <= len(digits) <= 19 and _luhn(digits):
                found.append("payment card number")
                break
    return found


_HARD = ("refactor", "architecture", "redesign", "migrate", "security audit", "vulnerab",
         "threat model", "implement feature", "implement a feature", "across the codebase",
         "root cause", "race condition", "performance regression", "compare", "research")
_MEDIUM = ("fix", "bug", "write test", "add test", "review", "debug", "implement", "explain why",
           "optimi", "document", "diff")
_EASY = ("git status", "list ", "summarize", "summarise", "rename", "format", "what does",
         "where is", "open ", "show me", "run tests", "typo")


def classify_complexity(task: str, est_context_tokens: int = 0, files_touched: int = 0) -> Complexity:
    t = task.lower()
    if any(k in t for k in _HARD) or files_touched >= 5 or est_context_tokens >= 40_000:
        return Complexity.HARD
    if any(k in t for k in _MEDIUM) or files_touched >= 2 or est_context_tokens >= 8_000:
        return Complexity.MEDIUM
    if any(k in t for k in _EASY) or len(t) < 80:
        return Complexity.EASY
    return Complexity.MEDIUM


# ---- routing -----------------------------------------------------------------------------

def route(task: str, sensitivity: Sensitivity, cfg: RouterConfig, *, est_context_tokens: int = 0,
          files_touched: int = 0, voice: bool = False, prefer: str | None = None,
          needs_web: bool = False) -> Decision:
    """prefer: None | "local" | "cloud". A preference can never override the privacy gate."""
    reasons: list[str] = []
    warnings: list[str] = []
    complexity = classify_complexity(task, est_context_tokens, files_touched)
    reasons.append(f"complexity={complexity.name}")

    hits = detect_sensitive(task, cfg.treat_pii_as_sensitive)
    effective = sensitivity
    if hits:
        effective = Sensitivity.SENSITIVE
        reasons.append("task text contains " + ", ".join(sorted(set(hits))))
    if sensitivity == Sensitivity.SENSITIVE:
        reasons.append("project classified sensitive")

    # 1. Privacy gate
    cloud_ok = cfg.allow_cloud and effective < Sensitivity.SENSITIVE
    blocked = False
    if prefer == "cloud" and not cloud_ok:
        blocked = True
        reasons.append("cloud requested but blocked by privacy policy" if effective == Sensitivity.SENSITIVE
                       else "cloud requested but allow_cloud is false")
    if needs_web and not cloud_ok:
        warnings.append("web/research needs network; stay local and use approved offline sources")

    # 2. Locality
    use_cloud = cloud_ok and prefer != "local"
    if use_cloud and prefer is None and complexity == Complexity.EASY:
        use_cloud = False
        reasons.append("easy task: local is cheaper, faster and keeps data on device")

    needs_confirmation = False
    if use_cloud and effective == Sensitivity.INTERNAL and cfg.cloud_confirm_internal:
        needs_confirmation = True
        reasons.append("internal project: confirm before sending to cloud")

    # 3. Strength
    if use_cloud:
        fast = complexity == Complexity.EASY or (voice and complexity < Complexity.HARD)
        tier = Tier.CLOUD_FAST if fast else Tier.CLOUD_STRONG
    else:
        fast = complexity == Complexity.EASY or (voice and complexity < Complexity.HARD)
        tier = Tier.LOCAL_FAST if fast else Tier.LOCAL_STRONG
        if est_context_tokens > cfg.local_context_limit:
            warnings.append(f"context ~{est_context_tokens} tokens exceeds local window "
                            f"({cfg.local_context_limit}); chunk the work or narrow the files")
        if complexity == Complexity.HARD and cfg.allow_cloud and effective >= Sensitivity.SENSITIVE:
            warnings.append("hard task kept local for privacy; expect weaker results, review carefully")
    if voice:
        reasons.append("voice turn: favouring low latency")

    profile = cfg.cloud_profile if tier.is_cloud else cfg.local_profile
    return Decision(tier=tier, profile=profile, alias=cfg.aliases[tier], complexity=complexity,
                    reasons=tuple(reasons), needs_confirmation=needs_confirmation,
                    warnings=tuple(warnings), blocked=blocked)
