"""Tests for core.recovery — error recovery mechanisms."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from src.core.recovery import RecoveryAction, RecoveryManager, RecoveryStrategy


@pytest.fixture
def mock_page():
    page = MagicMock()
    page.is_visible.return_value = False
    page.keyboard = MagicMock()
    return page


@pytest.fixture
def manager(mock_page):
    return RecoveryManager(mock_page)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestHandleError:
    def test_timeout_error(self, manager):
        error = PlaywrightTimeoutError("timeout")
        action = manager.handle_error(error, "test")
        assert action.strategy == RecoveryStrategy.WAIT_AND_RETRY
        assert action.wait_seconds > 0

    def test_timeout_exceeded(self, manager):
        error = PlaywrightTimeoutError("timeout")
        for _ in range(3):
            manager.handle_error(error, "test")
        action = manager.handle_error(error, "test")
        assert action.strategy == RecoveryStrategy.REFRESH

    def test_not_visible_error(self, manager):
        error = Exception("Element is not visible")
        action = manager.handle_error(error, "test")
        assert action.strategy == RecoveryStrategy.WAIT_AND_RETRY

    def test_navigation_error(self, manager):
        error = Exception("net::ERR_CONNECTION_REFUSED")
        action = manager.handle_error(error, "test")
        assert action.strategy == RecoveryStrategy.RETRY

    def test_navigation_exceeded(self, manager):
        error = Exception("net::ERR_CONNECTION_REFUSED")
        for _ in range(2):
            manager.handle_error(error, "test")
        action = manager.handle_error(error, "test")
        assert action.strategy == RecoveryStrategy.GO_BACK

    def test_selector_error(self, manager):
        error = Exception("Selector not found")
        action = manager.handle_error(error, "test")
        assert action.strategy == RecoveryStrategy.RETRY

    def test_generic_error_first(self, manager):
        error = Exception("something went wrong")
        action = manager.handle_error(error, "test")
        assert action.strategy == RecoveryStrategy.RETRY

    def test_generic_error_exceeded(self, manager):
        error = Exception("something went wrong")
        manager.handle_error(error, "test")
        action = manager.handle_error(error, "test")
        assert action.strategy == RecoveryStrategy.ABORT


# ---------------------------------------------------------------------------
# Recovery actions
# ---------------------------------------------------------------------------


class TestRecoveryActions:
    def test_dismiss_dialog(self, manager, mock_page):
        mock_page.is_visible.return_value = True
        result = manager.dismiss_dialog()
        assert result is True

    def test_dismiss_dialog_escape(self, manager, mock_page):
        mock_page.is_visible.return_value = False
        result = manager.dismiss_dialog()
        assert result is True
        mock_page.keyboard.press.assert_called_with("Escape")

    def test_wait_and_retry(self, manager):
        # Should not raise
        manager.wait_and_retry(0.01)

    def test_refresh_page(self, manager, mock_page):
        manager.refresh_page()
        mock_page.reload.assert_called_once()

    def test_go_back(self, manager, mock_page):
        manager.go_back()
        mock_page.go_back.assert_called_once()


# ---------------------------------------------------------------------------
# Execute recovery
# ---------------------------------------------------------------------------


class TestExecuteRecovery:
    def test_retry(self, manager):
        action = RecoveryAction(strategy=RecoveryStrategy.RETRY, reason="test")
        assert manager.execute_recovery(action) is True

    def test_wait_and_retry(self, manager):
        action = RecoveryAction(strategy=RecoveryStrategy.WAIT_AND_RETRY, reason="test", wait_seconds=0.01)
        assert manager.execute_recovery(action) is True

    def test_dismiss_dialog(self, manager, mock_page):
        mock_page.is_visible.return_value = True
        action = RecoveryAction(strategy=RecoveryStrategy.DISMISS_DIALOG, reason="test")
        assert manager.execute_recovery(action) is True

    def test_refresh(self, manager):
        action = RecoveryAction(strategy=RecoveryStrategy.REFRESH, reason="test")
        assert manager.execute_recovery(action) is True

    def test_go_back(self, manager):
        action = RecoveryAction(strategy=RecoveryStrategy.GO_BACK, reason="test")
        assert manager.execute_recovery(action) is True

    def test_skip(self, manager):
        action = RecoveryAction(strategy=RecoveryStrategy.SKIP, reason="test")
        assert manager.execute_recovery(action) is True

    def test_abort(self, manager):
        action = RecoveryAction(strategy=RecoveryStrategy.ABORT, reason="test")
        assert manager.execute_recovery(action) is False


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_counts(self, manager):
        error = PlaywrightTimeoutError("timeout")
        manager.handle_error(error, "test")
        manager.reset()
        assert manager._retry_counts == {}
