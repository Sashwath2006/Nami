import pytest

from nami.core.task_router import (Complexity, RouterConfig, Sensitivity, Tier,
                                     classify_complexity, detect_sensitive, route)

CLOUD = RouterConfig(allow_cloud=True)
LOCAL_ONLY = RouterConfig(allow_cloud=False)
HARD_TASK = "Refactor the architecture of the payment module across the codebase"


def test_sensitive_project_never_goes_to_cloud():
    d = route(HARD_TASK, Sensitivity.SENSITIVE, CLOUD)
    assert not d.tier.is_cloud and d.profile == "nami-local"


@pytest.mark.parametrize("text", [
    "debug this: api_key = abcd1234efgh5678",
    "my aws key AKIAABCDEFGHIJKLMNOP is failing",
    "-----BEGIN RSA PRIVATE KEY----- fix this",
    "email john.doe@example.com about the migration",
    "charge card 4111 1111 1111 1111 in the test",
    "ssn 123-45-6789 appears in the log",
])
def test_secrets_and_pii_in_task_force_local_even_for_public_project(text):
    d = route(text + " " + HARD_TASK, Sensitivity.PUBLIC, CLOUD)
    assert not d.tier.is_cloud
    assert any("contains" in r for r in d.reasons)


def test_non_luhn_number_is_not_flagged_as_card():
    assert "payment card number" not in detect_sensitive("order 1234 5678 9012 3456")


def test_cloud_disabled_forces_local():
    d = route(HARD_TASK, Sensitivity.PUBLIC, LOCAL_ONLY)
    assert d.tier == Tier.LOCAL_STRONG


def test_public_hard_task_uses_cloud_strong():
    d = route(HARD_TASK, Sensitivity.PUBLIC, CLOUD)
    assert d.tier == Tier.CLOUD_STRONG and d.profile == "nami-cloud" and not d.needs_confirmation


def test_public_easy_task_stays_local():
    d = route("git status", Sensitivity.PUBLIC, CLOUD)
    assert d.tier == Tier.LOCAL_FAST


def test_internal_cloud_requires_confirmation():
    d = route(HARD_TASK, Sensitivity.INTERNAL, CLOUD)
    assert d.tier.is_cloud and d.needs_confirmation


def test_prefer_cloud_cannot_override_privacy():
    d = route("explain this", Sensitivity.SENSITIVE, CLOUD, prefer="cloud")
    assert d.blocked and not d.tier.is_cloud


def test_prefer_cloud_blocked_when_cloud_disabled():
    d = route("explain this", Sensitivity.PUBLIC, LOCAL_ONLY, prefer="cloud")
    assert d.blocked and not d.tier.is_cloud


def test_prefer_local_respected():
    d = route(HARD_TASK, Sensitivity.PUBLIC, CLOUD, prefer="local")
    assert d.tier == Tier.LOCAL_STRONG


def test_voice_medium_task_uses_fast_tier():
    d = route("fix the bug in the parser", Sensitivity.PUBLIC, CLOUD, voice=True)
    assert d.tier == Tier.CLOUD_FAST


def test_large_context_warns_when_local():
    d = route("review this diff", Sensitivity.SENSITIVE, CLOUD, est_context_tokens=90_000)
    assert d.complexity == Complexity.HARD and any("exceeds local window" in w for w in d.warnings)


def test_files_touched_raises_complexity():
    assert classify_complexity("update names", files_touched=6) == Complexity.HARD


def test_command_uses_documented_flags():
    d = route("git status", Sensitivity.PUBLIC, CLOUD)
    assert d.hermes_command() == ["hermes", "-p", "nami-local", "chat", "--model", "local-fast"]


def test_log_record_never_contains_task_text():
    secret = "api_key = SUPERSECRETVALUE123"
    d = route(secret, Sensitivity.PUBLIC, CLOUD)
    assert "SUPERSECRETVALUE123" not in str(d.log_record())
