"""Pin browser-safe event handling in the SPA dashboard actions."""
from pathlib import Path

ROOT = Path(__file__).parents[1]
HTML = (ROOT / "src/ui/templates/index.html").read_text(encoding="utf-8-sig")
APP_JS = (ROOT / "src/ui/templates/assets/app.js").read_text(encoding="utf-8-sig")
BUNDLE = HTML + "\n" + APP_JS


def test_profile_actions_use_explicit_event_binding():
    # Row and drawer actions are bound with addEventListener (explicit targets),
    # not inline onclick with implicit window.event
    assert "bindRowEvents" in APP_JS
    assert "bindDrawerActions" in APP_JS
    assert "addEventListener" in APP_JS
    assert "window.event" not in APP_JS


def test_create_action_does_not_depend_on_implicit_window_event():
    # New-profile create is bound by id, handler takes no implicit event dependency
    assert 'id="np-create"' in HTML
    assert '"#np-create"' in APP_JS
    assert "event && event.target" not in APP_JS
