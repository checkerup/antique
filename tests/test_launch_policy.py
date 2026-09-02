"""Browser launch policies keep compatibility and stealth trade-offs explicit."""
import pytest

from src.core.launch_policy import LaunchPolicy, get_launch_policy


def test_google_compatible_policy_removes_known_login_blockers():
    policy = get_launch_policy("google-compatible")
    assert policy.name == "google-compatible"
    assert "--enable-automation" in policy.ignore_playwright_default_args
    assert "--no-sandbox" in policy.ignore_playwright_default_args
    assert "--no-sandbox" not in policy.chromium_args
    assert not any("disable-web-security" in arg for arg in policy.chromium_args)
    assert not any("AutomationControlled" in arg for arg in policy.chromium_args)


def test_standard_policy_keeps_playwright_defaults():
    policy = get_launch_policy("standard")
    assert policy.ignore_playwright_default_args == ()


def test_default_policy_is_google_compatible(monkeypatch):
    monkeypatch.delenv("ANTIQUE_LAUNCH_POLICY", raising=False)
    assert get_launch_policy().name == "google-compatible"


def test_environment_selects_policy(monkeypatch):
    monkeypatch.setenv("ANTIQUE_LAUNCH_POLICY", "stealth")
    assert get_launch_policy().name == "stealth"


def test_unknown_policy_fails_closed():
    with pytest.raises(ValueError, match="unknown launch policy"):
        get_launch_policy("unsafe-magic")


def test_policy_is_immutable():
    policy = get_launch_policy("standard")
    assert isinstance(policy, LaunchPolicy)
    with pytest.raises(Exception):
        policy.name = "changed"