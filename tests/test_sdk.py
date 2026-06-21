"""Tests for SDK — Python developer API."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core.agent_loop import AgentTaskResult
from src.core.script_store import reset_script_store
from src.sdk import AgentLoop, ScriptStore, run_task


@pytest.fixture
def mock_browser():
    with patch("src.sdk.get_browser_manager") as mock_get_bm:
        bm = MagicMock()
        bm.is_alive.return_value = True
        bm.get_page.return_value = MagicMock(url="https://example.com")
        mock_get_bm.return_value = bm
        yield bm


@pytest.fixture
def mock_agent():
    with patch("src.sdk._AgentLoop") as mock_cls:
        agent = MagicMock()
        agent.run.return_value = AgentTaskResult(success=True, task="test")
        mock_cls.return_value = agent
        yield agent


# ---------------------------------------------------------------------------
# AgentLoop
# ---------------------------------------------------------------------------


class TestAgentLoop:
    def test_run_success(self, mock_browser, mock_agent):
        with AgentLoop() as agent:
            result = agent.run("测试任务")
            assert result.success is True

    def test_run_launches_browser(self, mock_browser, mock_agent):
        bm = mock_browser
        bm.is_alive.return_value = False

        with AgentLoop(headless=True) as agent:
            agent.run("测试任务")
            bm.launch.assert_called_once_with(headless=True)

    def test_close(self, mock_browser):
        with patch("src.sdk.reset_browser_manager") as mock_reset:
            agent = AgentLoop()
            agent.close()
            mock_reset.assert_called_once()

    def test_context_manager(self, mock_browser, mock_agent):
        with patch("src.sdk.reset_browser_manager") as mock_reset:
            with AgentLoop() as agent:
                agent.run("测试任务")
            mock_reset.assert_called_once()

    def test_max_steps(self, mock_browser, mock_agent):
        with AgentLoop(max_steps=20) as agent:
            agent.run("测试任务")
            # Verify max_steps was passed


# ---------------------------------------------------------------------------
# ScriptStore
# ---------------------------------------------------------------------------


class TestScriptStoreSDK:
    def test_save_and_load(self, tmp_path):
        reset_script_store()
        store = ScriptStore(store_dir=tmp_path / "scripts")
        record = store.save("task", "script")
        assert store.load(record.id) is not None

    def test_search(self, tmp_path):
        reset_script_store()
        store = ScriptStore(store_dir=tmp_path / "scripts")
        store.save("搜索 Python", "script1")
        store.save("搜索 Java", "script2")
        assert len(store.search("搜索")) == 2

    def test_list_all(self, tmp_path):
        reset_script_store()
        store = ScriptStore(store_dir=tmp_path / "scripts")
        store.save("task1", "script1")
        store.save("task2", "script2")
        assert len(store.list_all()) == 2

    def test_delete(self, tmp_path):
        reset_script_store()
        store = ScriptStore(store_dir=tmp_path / "scripts")
        record = store.save("task", "script")
        assert store.delete(record.id) is True


# ---------------------------------------------------------------------------
# run_task convenience function
# ---------------------------------------------------------------------------


class TestRunTaskFunction:
    @patch("src.sdk.AgentLoop")
    def test_run_task(self, mock_cls):
        mock_agent = MagicMock()
        mock_agent.run.return_value = AgentTaskResult(success=True, task="test")
        mock_cls.return_value.__enter__ = MagicMock(return_value=mock_agent)
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        result = run_task("测试任务")
        assert result.success is True
