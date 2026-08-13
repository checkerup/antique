from dataclasses import replace

from src.core.detect import fingerprint_preview, score_fingerprint
from src.core.fingerprint import generate_fingerprint


def test_score_fingerprint_is_pure_and_structured():
    fp = generate_fingerprint(seed="iteration7")
    first = score_fingerprint(fp).to_dict()
    second = score_fingerprint(fp).to_dict()
    assert first == second
    assert 0 <= first["score"] <= 100
    assert first["total"] >= 10


def test_score_fingerprint_flags_webdriver():
    fp = generate_fingerprint(seed="webdriver")
    report = score_fingerprint(replace(fp, webdriver=True)).to_dict()
    failed = {item["name"] for item in report["failures"]}
    assert "webdriver_off" in failed
    assert report["ok"] is False


def test_score_fingerprint_flags_invalid_webrtc():
    fp = generate_fingerprint(seed="webrtc")
    report = score_fingerprint(replace(fp, webrtc_mode="proxy", webrtc_public_ip=None)).to_dict()
    assert "webrtc_mode_valid" in {item["name"] for item in report["failures"]}


def test_preview_groups_fields_and_report():
    fp = generate_fingerprint(seed="preview")
    preview = fingerprint_preview(fp)
    assert {group["title"] for group in preview["groups"]} >= {"Identity", "Graphics", "Network / WebRTC"}
    assert "score" in preview["report"]
    assert all("key" in field and "warn" in field for group in preview["groups"] for field in group["fields"])


def test_invalid_screen_is_reported():
    fp = generate_fingerprint(seed="screen")
    report = score_fingerprint(replace(fp, inner_width=99999)).to_dict()
    assert "screen_sanity" in {item["name"] for item in report["failures"]}
