"""
Python SDK —— 简洁的开发者 API。

提供 from agentic_playwright import AgentLoop 的简洁接口。

使用方式:
    from agentic_playwright import AgentLoop

    agent = AgentLoop()
    result = agent.run("帮我在百度搜索 Python 教程")
    print(result.output)
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from src.core.agent_loop import AgentLoop as _AgentLoop
from src.core.agent_loop import AgentTaskResult
from src.core.browser_manager import get_browser_manager, reset_browser_manager
from src.core.script_store import ScriptRecord, get_script_store
from src.core.vision import PageAnalysis


class AgentLoop:
    """简洁的 Agent 循环 API。

    使用方式::

        from agentic_playwright import AgentLoop

        agent = AgentLoop()
        result = agent.run("帮我在百度搜索 Python 教程")
        print(result.output)

        # 带选项
        agent = AgentLoop(max_steps=20, headless=True)
        result = agent.run("截图")
    """

    def __init__(
        self,
        max_steps: int = 10,
        headless: bool = False,
        use_cloak: bool = False,
        library_dir: str | Path | None = None,
        on_step: Callable | None = None,
    ) -> None:
        """初始化 Agent。

        Args:
            max_steps: 最大执行步数。
            headless: 是否无头模式。
            use_cloak: 是否使用 CloakBrowser。
            library_dir: 技能库目录。
            on_step: 每步回调函数。
        """
        self._max_steps = max_steps
        self._headless = headless
        self._use_cloak = use_cloak
        self._library_dir = library_dir
        self._on_step = on_step
        self._agent = None

    def run(self, task: str) -> AgentTaskResult:
        """执行任务。

        Args:
            task: 自然语言任务描述。

        Returns:
            AgentTaskResult。
        """
        # 确保浏览器已启动
        bm = get_browser_manager()
        if not bm.is_alive():
            bm.launch(headless=self._headless)

        # 创建 Agent
        self._agent = _AgentLoop(
            max_steps=self._max_steps,
            library_dir=self._library_dir,
            on_step=self._on_step,
        )

        return self._agent.run(task)

    def close(self) -> None:
        """关闭浏览器。"""
        reset_browser_manager()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ScriptStore:
    """脚本存储 API。"""

    def __init__(self, store_dir: str | Path | None = None) -> None:
        self._store = get_script_store(store_dir=store_dir)

    def save(self, task: str, script: str, tags: list[str] | None = None) -> ScriptRecord:
        """保存脚本。"""
        return self._store.save(task, script, tags)

    def load(self, script_id: str) -> ScriptRecord | None:
        """加载脚本。"""
        return self._store.load(script_id)

    def search(self, query: str) -> list[ScriptRecord]:
        """搜索脚本。"""
        return self._store.search(query)

    def list_all(self) -> list[ScriptRecord]:
        """列出所有脚本。"""
        return self._store.list_all()

    def delete(self, script_id: str) -> bool:
        """删除脚本。"""
        return self._store.delete(script_id)


# 便捷函数
def run_task(task: str, max_steps: int = 10, headless: bool = False) -> AgentTaskResult:
    """执行任务的便捷函数。

    Args:
        task: 任务描述。
        max_steps: 最大步数。
        headless: 是否无头模式。

    Returns:
        AgentTaskResult。
    """
    with AgentLoop(max_steps=max_steps, headless=headless) as agent:
        return agent.run(task)
