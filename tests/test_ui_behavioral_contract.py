"""Pin browser-safe event handling in inline dashboard actions."""
from pathlib import Path

HTML = (Path(__file__).parents[1] / "src/ui/templates/index.html").read_text(encoding="utf-8-sig")


def test_profile_actions_pass_the_clicked_button_explicitly():
    assert "act('start','${p.user_id}',this)" in HTML
    assert "act('stop','${p.user_id}',this)" in HTML
    assert "async function act(verb, id, btn = null)" in HTML


def test_create_action_does_not_depend_on_implicit_window_event():
    assert 'onclick="submitCreate(this)"' in HTML
    assert "async function submitCreate(btn = null)" in HTML
    assert "event && event.target" not in HTML
