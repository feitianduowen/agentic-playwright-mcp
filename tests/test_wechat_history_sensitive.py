from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.core.agent_loop import AgentTaskResult
from src.core.script_engine import ScriptEngine
from src.core.skill_router import SkillRouter
from src.desktop.database import DesktopDatabase
from src.desktop.events import DesktopEventHub
from src.desktop.sensitive_result_store import SensitiveResultStore
from src.desktop.task_service import (
    DesktopInteractionAdapter,
    DesktopTaskService,
    TaskControl,
    _is_wechat_desktop_task,
)
from src.layer_2.controls import get_controls_exports


def test_sensitive_result_store_is_memory_only_and_task_scoped(tmp_path: Path) -> None:
    database = DesktopDatabase(tmp_path / "desktop.db")
    database.create_conversation("conversation-1", "测试")
    database.add_message(
        "user-1",
        "conversation-1",
        role="user",
        message_type="user",
        content="读取微信记录",
        task_id="task-1",
    )
    database.create_task("task-1", "conversation-1", "user-1")
    service = DesktopTaskService(database, DesktopEventHub())
    adapter = DesktopInteractionAdapter(
        service, TaskControl(task_id="task-1", conversation_id="conversation-1")
    )
    raw_text = "这是不应写入 SQLite 的聊天原文"

    result_id = adapter.publish_sensitive_result(
        "wechat_history",
        {"chat": "张三", "messages": [{"content": raw_text}]},
    )

    assert service.sensitive_results.get(result_id, task_id="task-1") is not None
    persisted = database.list_messages("conversation-1")
    assert raw_text not in str(persisted)
    service.sensitive_results.delete_for_task("task-1")
    assert service.sensitive_results.get(result_id) is None
    service.shutdown()


def test_sensitive_result_store_expires_and_rejects_oversized_payload() -> None:
    store = SensitiveResultStore(max_entry_bytes=100)
    result_id = store.put(
        task_id="task",
        conversation_id="conversation",
        kind="wechat_history",
        payload={"messages": []},
        ttl_seconds=60,
    )
    entry = store._entries[result_id]
    entry.expires_at = time.monotonic() - 1
    assert store.get(result_id) is None

    try:
        store.put(
            task_id="task",
            conversation_id="conversation",
            kind="wechat_history",
            payload={"messages": [{"content": "x" * 1000}]},
        )
    except ValueError as exc:
        assert "size limit" in str(exc)
    else:
        raise AssertionError("oversized sensitive result was accepted")


def test_wechat_tasks_are_classified_as_desktop_only() -> None:
    assert _is_wechat_desktop_task("微信给张三发送你好")
    assert _is_wechat_desktop_task("读取我和张三最近 50 条聊天记录")
    assert _is_wechat_desktop_task("查看文件传输助手最近聊天记录")
    assert not _is_wechat_desktop_task("在知乎搜索微信聊天记录安全吗")


def test_desktop_wechat_task_does_not_launch_browser(tmp_path: Path) -> None:
    database = DesktopDatabase(tmp_path / "desktop.db")
    database.create_conversation("conversation-1", "微信任务")
    database.add_message(
        "user-1",
        "conversation-1",
        role="user",
        message_type="user",
        content="微信给张三发送你好",
        task_id="task-1",
    )
    database.create_task("task-1", "conversation-1", "user-1")
    service = DesktopTaskService(database, DesktopEventHub())
    control = TaskControl(task_id="task-1", conversation_id="conversation-1")
    browser = MagicMock()
    browser.is_alive.return_value = False
    agent = MagicMock()
    agent.run.return_value = AgentTaskResult(
        success=True,
        task="微信给张三发送你好",
        output="完成",
    )

    with (
        patch("src.desktop.task_service.get_browser_manager", return_value=browser),
        patch("src.desktop.task_service.AgentLoop", return_value=agent) as agent_class,
    ):
        service._run_task(control, "微信给张三发送你好")

    browser.launch.assert_not_called()
    assert agent_class.call_args.kwargs["desktop_only"] is True
    service.shutdown()


def test_history_skill_is_registered_and_returns_only_safe_metadata() -> None:
    assert "wechat_read_contact_history" in get_controls_exports()
    source = Path(
        "src/skill_library/read/wechat_read_contact_history.py"
    ).read_text(encoding="utf-8")
    raw_text = "secret message"
    calls: list[dict] = []
    engine = ScriptEngine()
    engine.register_functions(
        {
            "wechat_read_contact_history": lambda **kwargs: calls.append(kwargs)
            or {
                "success": True,
                "sensitive_result_id": "sensitive-id",
                "chat": "张三",
                "chat_type": "private",
                "count": 1,
                "meta_status": "ok",
                "messages": [{"content": raw_text}],
            },
            "log": lambda message: None,
        }
    )
    result = engine.execute(
        source + '\nresult = run(chat_name="张三", limit="1")\n'
    )

    assert result.success is True
    assert raw_text not in result.output
    assert calls[0]["chat_name"] == "张三"


def test_history_route_does_not_overlap_send_or_advice_routes() -> None:
    router = SkillRouter(library_dir="src/skill_library")
    positive = {
        "读取我和张三最近 50 条微信聊天记录": "张三",
        "查看我和张三从 2026-06-01 到 2026-06-30 的微信聊天": "张三",
        "看看项目讨论群最近 100 条消息": "项目讨论群",
        "读取文件传输助手最近 20 条聊天记录": "文件传输助手",
        "查看我和张三最近的文件消息": "张三",
        "总结我和张三最近 100 条微信聊天记录": "张三",
    }
    for task, chat_name in positive.items():
        decision = router.route(task)
        assert decision.skill is not None, task
        assert decision.skill.id == "domain/wechat_read_contact_history", task
        assert f'__param_chat_name = "{chat_name}"' in decision.script

    assert router.route("微信给张三发消息你好").skill.id == "domain/wechat_send_contact_message"
    assert router.route('微信给张三发文件"D:\\tmp\\a.txt"').skill.id == "domain/wechat_send_contact_file"
    for task in (
        "微信聊天记录怎么恢复",
        "不要读取张三的聊天记录",
        "删除我和张三的聊天记录",
        "微信聊天记录安全吗",
    ):
        decision = router.route(task)
        assert decision.skill is None or decision.skill.id != "domain/wechat_read_contact_history"


def test_missing_chat_name_uses_required_parameter_prompt() -> None:
    decision = SkillRouter(library_dir="src/skill_library").route("读取微信历史记录")
    assert decision.skill is not None
    assert decision.skill.id == "domain/wechat_read_contact_history"
    assert "panel_prompt" in decision.script
