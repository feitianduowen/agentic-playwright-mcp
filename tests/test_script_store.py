"""Tests for core.script_store — script persistence."""

from __future__ import annotations

import pytest

from src.core.script_store import ScriptRecord, ScriptStore, get_script_store, reset_script_store


@pytest.fixture
def store(tmp_path):
    return ScriptStore(store_dir=tmp_path / "scripts")


# ---------------------------------------------------------------------------
# ScriptRecord
# ---------------------------------------------------------------------------


class TestScriptRecord:
    def test_success_rate(self):
        record = ScriptRecord(id="test", task="test", script="test", use_count=10, success_count=7)
        assert record.success_rate == 0.7

    def test_success_rate_zero(self):
        record = ScriptRecord(id="test", task="test", script="test")
        assert record.success_rate == 0.0

    def test_to_dict(self):
        record = ScriptRecord(id="test", task="test", script="print('hello')")
        d = record.to_dict()
        assert d["id"] == "test"
        assert d["task"] == "test"

    def test_from_dict(self):
        d = {"id": "test", "task": "test", "script": "print('hello')"}
        record = ScriptRecord.from_dict(d)
        assert record.id == "test"


# ---------------------------------------------------------------------------
# ScriptStore
# ---------------------------------------------------------------------------


class TestScriptStore:
    def test_save_and_load(self, store):
        record = store.save("搜索 Python", 'goto("https://baidu.com")')
        assert record.id is not None
        assert record.task == "搜索 Python"

        loaded = store.load(record.id)
        assert loaded is not None
        assert loaded.script == 'goto("https://baidu.com")'

    def test_save_overwrite(self, store):
        store.save("搜索 Python", "v1")
        record = store.save("搜索 Python", "v2")
        assert record.script == "v2"

    def test_search(self, store):
        store.save("搜索 Python 教程", "script1")
        store.save("搜索 Java 教程", "script2")
        store.save("登录 GitHub", "script3")

        results = store.search("搜索")
        assert len(results) == 2

    def test_list_all(self, store):
        store.save("task1", "script1")
        store.save("task2", "script2")
        assert len(store.list_all()) == 2

    def test_delete(self, store):
        record = store.save("task", "script")
        assert store.delete(record.id) is True
        assert store.load(record.id) is None

    def test_delete_nonexistent(self, store):
        assert store.delete("nonexistent") is False

    def test_record_usage(self, store):
        record = store.save("task", "script")
        store.record_usage(record.id, True)
        store.record_usage(record.id, True)
        store.record_usage(record.id, False)

        loaded = store.load(record.id)
        assert loaded.use_count == 3
        assert loaded.success_count == 2

    def test_find_by_task(self, store):
        store.save("搜索 Python", "script")
        record = store.find_by_task("搜索 Python")
        assert record is not None

    def test_find_by_task_not_found(self, store):
        record = store.find_by_task("不存在的任务")
        assert record is None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def teardown_method(self):
        reset_script_store()

    def test_singleton(self, tmp_path):
        s1 = get_script_store(store_dir=tmp_path / "scripts")
        s2 = get_script_store()
        assert s1 is s2

    def test_reset(self, tmp_path):
        s1 = get_script_store(store_dir=tmp_path / "scripts")
        reset_script_store()
        s2 = get_script_store(store_dir=tmp_path / "scripts")
        assert s1 is not s2
