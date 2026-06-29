"""Tests for the Bilibili search skill adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from src.core.script_engine import ScriptEngine
from src.skill_library.search.bilibili_search import _fill_and_submit, run


def _noop(*args):
    return "ok"


def _with_page(html, callback):
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                page = browser.new_page(viewport={"width": 1200, "height": 800})
                page.set_content(html)
                return callback(page)
            finally:
                browser.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright browser unavailable: {exc}")


def test_bilibili_search_opens_home_fills_and_submits():
    urls = []
    js_calls = []
    logs = []
    current_url = {"value": "https://search.bilibili.com/all?keyword=test"}

    def goto(url):
        urls.append(url)
        current_url["value"] = url
        return "ok"

    def run_js(code):
        js_calls.append(code)
        current_url["value"] = "https://search.bilibili.com/all?keyword=test"
        return {"success": True, "filled": True, "clicked": True, "value": "test"}

    result = run(
        "test",
        goto_fn=goto,
        run_js_fn=run_js,
        wait_fn=_noop,
        wait_for_navigation_fn=_noop,
        get_url_fn=lambda: current_url["value"],
        log_fn=lambda message: logs.append(message),
    )

    assert result["success"] is True
    assert urls == ["https://www.bilibili.com"]
    assert len(js_calls) == 1
    assert ".nav-search-input" in js_calls[0]
    assert ".nav-search-btn" in js_calls[0]
    assert "button.click()" in js_calls[0]
    assert logs == ["Bilibili 搜索完成: test"]


def test_bilibili_search_falls_back_to_result_url_after_interactive_submit():
    urls = []
    current_url = {"value": "https://www.bilibili.com"}

    def goto(url):
        urls.append(url)
        current_url["value"] = url
        return "ok"

    result = run(
        "机器学习",
        goto_fn=goto,
        run_js_fn=lambda code: {"success": True, "filled": True, "clicked": True},
        wait_fn=_noop,
        wait_for_navigation_fn=_noop,
        get_url_fn=lambda: current_url["value"],
        log_fn=_noop,
    )

    assert result["success"] is True
    assert urls == [
        "https://www.bilibili.com",
        "https://search.bilibili.com/all?keyword=%E6%9C%BA%E5%99%A8%E5%AD%A6%E4%B9%A0",
    ]


def test_bilibili_fill_and_submit_writes_input_and_clicks_button():
    html = """
    <body>
      <input id="wrong" placeholder="手机号" style="width:200px;height:32px" />
      <div class="center-search-container">
        <input class="nav-search-input" placeholder="搜索"
          style="width:300px;height:34px" />
        <button class="nav-search-btn" style="width:60px;height:34px">搜索</button>
      </div>
      <div id="clicked">no</div>
      <script>
        document.querySelector('.nav-search-btn').addEventListener('click', () => {
          document.getElementById('clicked').textContent =
            document.querySelector('.nav-search-input').value;
        });
      </script>
    </body>
    """

    def assert_page(page):
        result = _fill_and_submit(lambda code: page.evaluate(code), "机器学习")

        assert result["success"] is True
        assert result["filled"] is True
        assert result["clicked"] is True
        assert page.locator(".nav-search-input").input_value() == "机器学习"
        assert page.locator("#wrong").input_value() == ""
        assert page.locator("#clicked").text_content() == "机器学习"

    _with_page(html, assert_page)


def test_bilibili_search_uses_enter_and_result_url_when_button_missing():
    urls = []
    current_url = {"value": "https://www.bilibili.com"}

    def goto(url):
        urls.append(url)
        current_url["value"] = url
        return "ok"

    html = """
    <body>
      <form class="center-search-container" onsubmit="event.preventDefault()">
        <input class="nav-search-input" placeholder="搜索"
          style="width:300px;height:34px" />
      </form>
    </body>
    """

    def assert_page(page):
        result = run(
            "python",
            goto_fn=goto,
            run_js_fn=lambda code: page.evaluate(code),
            wait_fn=_noop,
            wait_for_navigation_fn=_noop,
            get_url_fn=lambda: current_url["value"],
            log_fn=_noop,
        )

        assert result["success"] is True
        assert urls == [
            "https://www.bilibili.com",
            "https://search.bilibili.com/all?keyword=python",
        ]
        assert page.locator(".nav-search-input").input_value() == "python"

    _with_page(html, assert_page)


def test_bilibili_search_source_runs_inside_script_engine():
    source = Path("src/skill_library/search/bilibili_search.py").read_text(
        encoding="utf-8"
    )
    urls = []
    logs = []
    current_url = {"value": "https://search.bilibili.com/all?keyword=test"}
    engine = ScriptEngine()
    engine.register_functions(
        {
            "goto": lambda url: urls.append(url) or "ok",
            "run_js": lambda code: {"success": True, "filled": True, "clicked": True},
            "wait": _noop,
            "wait_for_navigation": _noop,
            "get_url": lambda: current_url["value"],
            "log": lambda message: logs.append(message),
        }
    )

    result = engine.execute(source + '\nresult = run("test")\nprint(result)\n')

    assert result.success is True
    assert urls == ["https://www.bilibili.com"]
    assert logs == ["Bilibili 搜索完成: test"]
    assert "'success': True" in result.output
