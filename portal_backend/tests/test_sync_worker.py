"""Tests for the cron onboard_students module (replaced the old SyncWorker)."""

from unittest.mock import patch

from app.cron.onboard_students import _build_activation_url, _is_zk_course


def test_is_zk_course_detects_zk():
    assert _is_zk_course("ZK Cohort XIV") is True
    assert _is_zk_course("Zero Knowledge Bootcamp") is True
    assert _is_zk_course("zero-knowledge program") is True


def test_is_zk_course_rejects_non_zk():
    assert _is_zk_course("Web3 Cohort XIV") is False
    assert _is_zk_course("Rust Masterclass") is False
    assert _is_zk_course("Web2 Bootcamp") is False
    assert _is_zk_course(None) is False


def test_build_activation_url():
    with patch("app.cron.onboard_students.settings") as mock_settings:
        mock_settings.PORTAL_FRONTEND_URL = "https://portal.example.com"
        url = _build_activation_url("abc123")
        assert url == "https://portal.example.com/activate?token=abc123"


def test_build_activation_url_strips_trailing_slash():
    with patch("app.cron.onboard_students.settings") as mock_settings:
        mock_settings.PORTAL_FRONTEND_URL = "https://portal.example.com/"
        url = _build_activation_url("abc123")
        assert url == "https://portal.example.com/activate?token=abc123"
