"""
Agentic Playwright MCP Server -- main entry point.

Registers browser-automation tools via FastMCP and exposes them to MCP
clients (e.g. Claude Desktop).  All tools return synchronously using
Playwright's sync_api.
"""

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from src.core.browser_manager import get_browser_manager
from src.layer_1.actions import do_goto, do_click, do_screenshot
from src.layer_3.domain_loader import load_domain, get_element_selectors
from src.layer_3.config_updater import update_selector_priority

# ---------------------------------------------------------------------------
# MCP Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="agentic-playwright-mcp",
)

# ---------------------------------------------------------------------------
# Project path constants (for locating the domains/ directory)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DOMAINS_DIR = str(_PROJECT_ROOT / "domains")


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


@mcp.tool()
def ping() -> str:
    """Health-check endpoint.  Returns 'pong'."""
    return "pong"


@mcp.tool()
def browser_launch() -> str:
    """Launch a Chromium browser and return its status.

    Uses the BrowserManager singleton.  If a browser is already running,
    returns an informational message instead of launching a second one.
    """
    bm = get_browser_manager()

    if bm.is_alive():
        return "Browser is already running."

    try:
        headless = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
        page = bm.launch(headless=headless)
        url = page.url
        return f"Browser launched successfully. Current page: {url}"
    except Exception as exc:
        return f"Browser launch failed: {exc}"


@mcp.tool()
def navigate(url: str) -> str:
    """Navigate to the given URL.

    Args:
        url: Target web address.

    Returns:
        A description of the navigation result.
    """
    bm = get_browser_manager()
    try:
        page = bm.get_page()
    except RuntimeError:
        return "Browser not launched. Call browser_launch first."

    return do_goto(page, url)


@mcp.tool()
def smart_click(element_name: str, domain: str = "default") -> str:
    """Smart click: locate an element via domain config and click it.

    Loads domains/{domain}.yaml, extracts the selector list for
    *element_name*, and tries each selector in priority order.  If a
    fallback selector succeeds (index > 0), the YAML is automatically
    updated to promote that selector (self-healing mechanism).

    Args:
        element_name: Key in the YAML 'locators' dict, e.g. 'search_button'.
        domain: Domain config filename (without .yaml extension).

    Returns:
        A description of the click outcome.
    """
    bm = get_browser_manager()
    try:
        page = bm.get_page()
    except RuntimeError:
        return "Browser not launched. Call browser_launch first."

    # 1. Load domain config and extract selector list
    try:
        domain_config = load_domain(domain, domains_dir=_DOMAINS_DIR)
    except FileNotFoundError as exc:
        return f"Domain config load failed: {exc}"
    except Exception as exc:
        return f"Domain config parse error: {exc}"

    try:
        selector_list = get_element_selectors(domain_config, element_name)
    except ValueError as exc:
        return str(exc)

    if not selector_list:
        return f"Selector list for element '{element_name}' is empty."

    # 2. Execute click
    result = do_click(page, selector_list)

    if not result.get("success"):
        return f"Click failed: {result.get('error', 'unknown error')}"

    used_selector = result["used_selector"]
    index = result["index"]

    # 3. Self-heal: promote the selector if it was a fallback
    if index > 0:
        updated = update_selector_priority(
            domain_name=domain,
            element_name=element_name,
            successful_selector=used_selector,
            domains_dir=_DOMAINS_DIR,
        )
        heal_msg = (
            " (selector priority auto-updated)"
            if updated
            else " (priority update failed)"
        )
    else:
        heal_msg = ""

    return (
        f"Click succeeded: element='{element_name}', "
        f"selector='{used_selector}' (index={index}){heal_msg}"
    )


@mcp.tool()
def screenshot(path: str) -> str:
    """Capture a screenshot of the current page and save it.

    Args:
        path: File path for the screenshot (PNG), e.g. 'screenshots/home.png'.

    Returns:
        The save-result message.
    """
    bm = get_browser_manager()
    try:
        page = bm.get_page()
    except RuntimeError:
        return "Browser not launched. Call browser_launch first."

    try:
        saved = do_screenshot(page, path)
        return f"Screenshot saved: {saved}"
    except Exception as exc:
        return f"Screenshot failed: {exc}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Start the MCP stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
