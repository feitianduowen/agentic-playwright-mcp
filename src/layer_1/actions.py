"""
Layer 1 — 基础原语（Helpers）。

提供页面导航、元素点击、文本填充、截图等原子操作。
所有选择器通过列表传入，按顺序尝试，实现自愈逻辑。
严禁在本模块中硬编码任何 XPath / CSS 选择器。
"""

import os
import time
from typing import List

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


def do_goto(page: Page, url: str) -> str:
    """导航到指定 URL。

    Args:
        page: Playwright 页面实例。
        url: 目标 URL。

    Returns:
        描述导航结果的状态字符串。
    """
    try:
        response = page.goto(url, wait_until="domcontentloaded")
        status = response.status if response else "unknown"
        return f"导航成功: {url} (HTTP {status})"
    except PlaywrightTimeoutError:
        return f"导航超时: {url}"
    except Exception as exc:
        return f"导航失败: {url} — {exc}"


def do_click(
    page: Page,
    selector_list: List[str],
    timeout: int = 5000,
) -> dict:
    """点击元素，支持多选择器自愈。

    按顺序尝试 selector_list 中的每个选择器：
    1. 先用 is_visible 短超时探测可见性
    2. 可见则执行 click 并立即返回成功
    3. 全部失败则截屏并返回错误信息

    Args:
        page: Playwright 页面实例。
        selector_list: 候选选择器列表（CSS / text= / role= 等）。
        timeout: 单次点击的超时时间（毫秒）。

    Returns:
        dict: 成功时含 success, used_selector, index；
              失败时含 success, error, screenshot。
    """
    for i, selector in enumerate(selector_list):
        try:
            if page.is_visible(selector, timeout=1000):
                page.click(selector, timeout=timeout)
                return {
                    "success": True,
                    "used_selector": selector,
                    "index": i,
                }
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    # 所有选择器均失败 — 截屏留证
    screenshot_path = _save_error_screenshot(page, "click")
    return {
        "success": False,
        "error": f"所有选择器均不可用: {selector_list}",
        "screenshot": screenshot_path,
    }


def do_fill(
    page: Page,
    selector_list: List[str],
    value: str,
    timeout: int = 5000,
) -> dict:
    """填充文本到输入框，支持多选择器自愈。

    自愈逻辑与 do_click 一致：按顺序尝试选择器列表，
    找到可见目标后执行 fill 操作。

    Args:
        page: Playwright 页面实例。
        selector_list: 候选选择器列表。
        value: 要填入的文本内容。
        timeout: 单次填充的超时时间（毫秒）。

    Returns:
        dict: 成功时含 success, used_selector, index；
              失败时含 success, error, screenshot。
    """
    for i, selector in enumerate(selector_list):
        try:
            if page.is_visible(selector, timeout=1000):
                page.fill(selector, value, timeout=timeout)
                return {
                    "success": True,
                    "used_selector": selector,
                    "index": i,
                }
        except PlaywrightTimeoutError:
            continue
        except Exception:
            continue

    screenshot_path = _save_error_screenshot(page, "fill")
    return {
        "success": False,
        "error": f"所有选择器均不可用: {selector_list}",
        "screenshot": screenshot_path,
    }


def do_screenshot(page: Page, path: str) -> str:
    """对当前页面截图并保存到指定路径。

    自动创建目标目录（如果不存在）。

    Args:
        page: Playwright 页面实例。
        path: 截图保存路径（PNG 格式）。

    Returns:
        实际保存的文件路径。
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    page.screenshot(path=path, full_page=True)
    return path


def _save_error_screenshot(page: Page, action: str) -> str:
    """保存错误截图到 logs/ 目录。

    文件名格式: logs/error_{action}_{timestamp}.png

    Args:
        page: Playwright 页面实例。
        action: 触发截图的操作名称（如 click, fill）。

    Returns:
        截图文件路径，截屏本身失败时返回空字符串。
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_dir = "logs"
    os.makedirs(log_dir, exist_ok=True)
    path = os.path.join(log_dir, f"error_{action}_{timestamp}.png")
    try:
        page.screenshot(path=path, full_page=True)
        return path
    except Exception:
        return ""
