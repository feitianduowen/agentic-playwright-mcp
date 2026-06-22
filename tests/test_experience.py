"""Tests for core.experience — experience evolution system."""

from __future__ import annotations

import pytest

from src.core.experience import (
    ExperienceManager,
    SelectorExperience,
    ScriptRecord,
    SiteKnowledge,
    get_experience_manager,
    reset_experience_manager,
)


@pytest.fixture
def manager(tmp_path):
    return ExperienceManager(workspace_dir=tmp_path / "workspace")


# ---------------------------------------------------------------------------
# Script management
# ---------------------------------------------------------------------------


class TestScriptManagement:
    def test_save_and_find(self, manager):
        record = manager.save_script("搜索 Python", 'goto("https://baidu.com")')
        assert record.id is not None

        found = manager.find_script("搜索 Python")
        assert found is not None
        assert found.script == 'goto("https://baidu.com")'

    def test_find_similar(self, manager):
        manager.save_script("在百度搜索 Python 教程", "script1")
        manager.save_script("在百度搜索 Java 教程", "script2")

        # 相似匹配
        found = manager.find_script("在百度搜索 Python")
        assert found is not None

    def test_record_usage(self, manager):
        record = manager.save_script("task", "script")
        manager.record_script_usage(record.id, True)
        manager.record_script_usage(record.id, True)
        manager.record_script_usage(record.id, False)

        found = manager.find_script("task")
        assert found.use_count == 3
        assert found.success_count == 2
        assert found.success_rate == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# Selector experience
# ---------------------------------------------------------------------------


class TestSelectorExperience:
    def test_record_success(self, manager):
        manager.record_selector_success("baidu", "search_input", "#kw")
        manager.record_selector_success("baidu", "search_input", "#kw")

        best = manager.get_best_selectors("baidu", "search_input")
        assert best == ["#kw"]

    def test_record_failure(self, manager):
        manager.record_selector_success("baidu", "search_input", "#kw")
        manager.record_selector_failure("baidu", "search_input", ".old-selector")

        best = manager.get_best_selectors("baidu", "search_input")
        assert best[0] == "#kw"  # 更可靠

    def test_reliability_score(self):
        exp = SelectorExperience(selector="#kw", site="baidu", element="input")
        assert exp.reliability == 0.5  # 无经验时默认 0.5

        exp.success_count = 8
        exp.fail_count = 2
        assert exp.reliability == 0.8


# ---------------------------------------------------------------------------
# Site knowledge
# ---------------------------------------------------------------------------


class TestSiteKnowledge:
    def test_add_gotcha(self, manager):
        manager.add_knowledge("baidu", gotcha="headless 模式下搜索框隐藏")
        knowledge = manager.get_knowledge("baidu")
        assert knowledge is not None
        assert "headless 模式下搜索框隐藏" in knowledge.gotchas

    def test_add_pattern(self, manager):
        manager.add_knowledge("baidu", pattern="用 JS 方式填写搜索框")
        knowledge = manager.get_knowledge("baidu")
        assert "用 JS 方式填写搜索框" in knowledge.patterns

    def test_no_duplicate(self, manager):
        manager.add_knowledge("baidu", gotcha="test")
        manager.add_knowledge("baidu", gotcha="test")
        knowledge = manager.get_knowledge("baidu")
        assert len(knowledge.gotchas) == 1


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


class TestStats:
    def test_get_stats(self, manager):
        manager.save_script("task1", "script1")
        manager.record_selector_success("baidu", "input", "#kw")
        manager.add_knowledge("baidu", gotcha="test")

        stats = manager.get_stats()
        assert stats["scripts"] == 1
        assert stats["selector_experiences"] == 1
        assert stats["sites_with_knowledge"] == 1


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def teardown_method(self):
        reset_experience_manager()

    def test_singleton(self, tmp_path):
        m1 = get_experience_manager(workspace_dir=tmp_path / "ws")
        m2 = get_experience_manager()
        assert m1 is m2

    def test_reset(self, tmp_path):
        m1 = get_experience_manager(workspace_dir=tmp_path / "ws")
        reset_experience_manager()
        m2 = get_experience_manager(workspace_dir=tmp_path / "ws")
        assert m1 is not m2
