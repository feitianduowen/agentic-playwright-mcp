"""
Playwright 浏览器生命周期管理器。

提供单例模式的 BrowserManager，负责启动/关闭 Chromium 浏览器实例。
所有页面操作通过 get_page() 获取统一入口。
"""

from playwright.sync_api import sync_playwright, Page


_instance: "BrowserManager | None" = None


class BrowserManager:
    """Playwright 浏览器生命周期管理器（单例）。"""

    def __init__(self) -> None:
        self._playwright = None
        self._browser = None
        self._page = None

    def launch(self, headless: bool = False, slow_mo: int = 500) -> Page:
        """启动 Chromium 浏览器并返回默认页面。

        Args:
            headless: 是否无头模式运行。
            slow_mo: 操作间延迟（毫秒），便于观察和调试。

        Returns:
            启动后的默认 Page 实例。
        """
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
        )
        self._page = self._browser.new_page()
        return self._page

    def get_page(self) -> Page:
        """返回当前活跃页面。

        Returns:
            当前 Page 实例。

        Raises:
            RuntimeError: 浏览器尚未启动时抛出。
        """
        if self._page is None:
            raise RuntimeError(
                "浏览器尚未启动，请先调用 launch() 方法。"
            )
        return self._page

    def close(self) -> None:
        """关闭浏览器和 Playwright 实例。安全处理已关闭的情况。"""
        try:
            if self._browser is not None:
                self._browser.close()
        except Exception:
            pass
        finally:
            self._browser = None
            self._page = None

        try:
            if self._playwright is not None:
                self._playwright.stop()
        except Exception:
            pass
        finally:
            self._playwright = None

    def is_alive(self) -> bool:
        """检查浏览器是否仍在运行。

        Returns:
            浏览器已启动且连接有效时返回 True。
        """
        if self._browser is None:
            return False
        try:
            # 通过尝试获取上下文来验证连接是否存活
            _ = self._browser.contexts
            return True
        except Exception:
            return False


def get_browser_manager() -> BrowserManager:
    """获取全局单例 BrowserManager 实例。

    Returns:
        全局唯一的 BrowserManager 实例。
    """
    global _instance
    if _instance is None:
        _instance = BrowserManager()
    return _instance
