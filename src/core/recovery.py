"""
错误恢复模块 —— 处理常见的浏览器自动化失败场景。

支持的恢复策略:
- 弹窗/对话框处理
- 页面超时重试
- 元素不可见等待
- 导航失败重试
- 选择器降级
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


class RecoveryStrategy(str, Enum):
    """恢复策略。"""

    RETRY = "retry"  # 重试当前操作
    WAIT_AND_RETRY = "wait_and_retry"  # 等待后重试
    DISMISS_DIALOG = "dismiss_dialog"  # 关闭弹窗
    REFRESH = "refresh"  # 刷新页面
    GO_BACK = "go_back"  # 后退
    SKIP = "skip"  # 跳过当前步骤
    ABORT = "abort"  # 中止任务


@dataclass
class RecoveryAction:
    """恢复动作。"""

    strategy: RecoveryStrategy
    reason: str
    wait_seconds: float = 0.0
    max_retries: int = 3


class RecoveryManager:
    """错误恢复管理器。"""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._retry_counts: dict[str, int] = {}

    def handle_error(self, error: Exception, context: str = "") -> RecoveryAction:
        """根据错误类型决定恢复策略。

        Args:
            error: 异常对象。
            context: 错误上下文。

        Returns:
            RecoveryAction。
        """
        error_type = type(error).__name__
        error_msg = str(error).lower()

        # 弹窗/对话框
        if "dialog" in error_msg or "alert" in error_msg:
            return RecoveryAction(
                strategy=RecoveryStrategy.DISMISS_DIALOG,
                reason="检测到弹窗，尝试关闭",
            )

        # 超时
        if isinstance(error, PlaywrightTimeoutError) or "timeout" in error_msg:
            retry_key = f"timeout_{context}"
            count = self._retry_counts.get(retry_key, 0)
            if count < 3:
                self._retry_counts[retry_key] = count + 1
                return RecoveryAction(
                    strategy=RecoveryStrategy.WAIT_AND_RETRY,
                    reason=f"超时，等待后重试 ({count + 1}/3)",
                    wait_seconds=2.0 * (count + 1),
                )
            else:
                return RecoveryAction(
                    strategy=RecoveryStrategy.REFRESH,
                    reason="多次超时，刷新页面",
                )

        # 元素不可见
        if "not visible" in error_msg or "not attached" in error_msg:
            return RecoveryAction(
                strategy=RecoveryStrategy.WAIT_AND_RETRY,
                reason="元素不可见，等待后重试",
                wait_seconds=1.0,
            )

        # 导航失败
        if "navigation" in error_msg or "net::" in error_msg:
            retry_key = f"nav_{context}"
            count = self._retry_counts.get(retry_key, 0)
            if count < 2:
                self._retry_counts[retry_key] = count + 1
                return RecoveryAction(
                    strategy=RecoveryStrategy.RETRY,
                    reason=f"导航失败，重试 ({count + 1}/2)",
                )
            else:
                return RecoveryAction(
                    strategy=RecoveryStrategy.GO_BACK,
                    reason="多次导航失败，后退",
                )

        # 选择器错误
        if "selector" in error_msg or "locator" in error_msg:
            return RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                reason="选择器错误，重试",
            )

        # 默认：重试一次
        retry_key = f"generic_{context}"
        count = self._retry_counts.get(retry_key, 0)
        if count < 1:
            self._retry_counts[retry_key] = count + 1
            return RecoveryAction(
                strategy=RecoveryStrategy.RETRY,
                reason=f"未知错误，重试 ({count + 1}/1)",
            )

        return RecoveryAction(
            strategy=RecoveryStrategy.ABORT,
            reason=f"无法恢复: {error_type}: {error_msg[:100]}",
        )

    def dismiss_dialog(self) -> bool:
        """尝试关闭弹窗/对话框。

        Returns:
            是否成功关闭。
        """
        try:
            # 尝试点击常见的关闭按钮
            dismiss_selectors = [
                "button[aria-label='Close']",
                "button.close",
                ".modal-close",
                "[data-dismiss='modal']",
                "text=关闭",
                "text=Close",
                "text=确定",
                "text=OK",
                "text=Cancel",
            ]

            for selector in dismiss_selectors:
                try:
                    if self._page.is_visible(selector, timeout=500):
                        self._page.click(selector, timeout=1000)
                        time.sleep(0.5)
                        return True
                except Exception:
                    continue

            # 尝试按 Escape 键
            self._page.keyboard.press("Escape")
            time.sleep(0.5)
            return True

        except Exception:
            return False

    def wait_and_retry(self, seconds: float) -> None:
        """等待后重试。"""
        time.sleep(seconds)

    def refresh_page(self) -> None:
        """刷新页面。"""
        try:
            self._page.reload(wait_until="domcontentloaded", timeout=10000)
        except Exception:
            pass

    def go_back(self) -> None:
        """后退。"""
        try:
            self._page.go_back(wait_until="domcontentloaded", timeout=10000)
        except Exception:
            pass

    def execute_recovery(self, action: RecoveryAction) -> bool:
        """执行恢复动作。

        Args:
            action: 恢复动作。

        Returns:
            是否成功恢复。
        """
        if action.strategy == RecoveryStrategy.DISMISS_DIALOG:
            return self.dismiss_dialog()

        if action.strategy == RecoveryStrategy.WAIT_AND_RETRY:
            self.wait_and_retry(action.wait_seconds)
            return True

        if action.strategy == RecoveryStrategy.REFRESH:
            self.refresh_page()
            return True

        if action.strategy == RecoveryStrategy.GO_BACK:
            self.go_back()
            return True

        if action.strategy == RecoveryStrategy.RETRY:
            return True

        if action.strategy == RecoveryStrategy.SKIP:
            return True

        if action.strategy == RecoveryStrategy.ABORT:
            return False

        return False

    def reset(self) -> None:
        """重置重试计数。"""
        self._retry_counts.clear()
