"""Tests for the Bilibili article publish skill adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from src.core.script_engine import ScriptEngine
from src.skill_library.send.bilibili_publish import _click_publish, _fill_article, run


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


def _mock_publish_run_js(title="测试标题", body="测试正文"):
    def run_js(code):
        if "logged_in:" in code:
            return {"success": True, "logged_in": True}
        if "ready:" in code and "hasTitle" in code:
            return {"success": True, "ready": True}
        if "title_value" in code:
            return {
                "success": True,
                "title_value": title,
                "body_value": body,
                "title_selector": "标题",
                "body_selector": "正文",
            }
        if "PUBLISH_TEXT" in code:
            return {"success": True, "text": "发布", "method": "bottom_right_publish_button"}
        return {"success": True}

    return run_js


def test_bilibili_publish_runs_when_already_logged_in():
    urls = []
    logs = []

    result = run(
        "13574133406",
        "测试标题",
        "测试正文",
        max_wait_seconds=0,
        goto_fn=lambda url: urls.append(url) or "ok",
        run_js_fn=_mock_publish_run_js(),
        wait_fn=_noop,
        get_url_fn=lambda: "https://member.bilibili.com/platform/upload/text/new-article",
        get_text_fn=lambda: "",
        log_fn=lambda message: logs.append(message),
    )

    assert result["success"] is True
    assert urls == ["https://member.bilibili.com/platform/upload/text/new-article"]
    assert result["title"] == "测试标题"
    assert result["body"] == "测试正文"
    assert logs == ["Bilibili article publish button clicked"]


def test_bilibili_publish_fills_title_body_and_clicks_publish():
    html = """
    <body>
      <input id="search" placeholder="搜索" style="width:240px;height:32px" />
      <input id="title" placeholder="请输入标题" style="width:400px;height:36px" />
      <div id="body" class="ql-editor" contenteditable="true"
        data-placeholder="请输入正文"
        style="width:600px;height:220px;border:1px solid #ddd"></div>
      <button id="publish" style="position:fixed;right:24px;bottom:24px;
        width:96px;height:36px;background:#00a1d6;color:white">发布</button>
      <div id="published">no</div>
      <script>
        document.getElementById('publish').addEventListener('click', () => {
          document.getElementById('published').textContent =
            document.getElementById('title').value + '|' + document.getElementById('body').innerText;
        });
      </script>
    </body>
    """

    def assert_page(page):
        fill_result = _fill_article(
            lambda code: page.evaluate(code),
            "我的标题",
            "第一行正文\n第二行正文",
        )
        publish_result = _click_publish(lambda code: page.evaluate(code))

        assert fill_result["success"] is True
        assert publish_result["success"] is True
        assert publish_result["method"] == "bottom_right_publish_button"
        assert page.locator("#title").input_value() == "我的标题"
        assert page.locator("#body").inner_text() == "第一行正文\n第二行正文"
        assert page.locator("#search").input_value() == ""
        assert "我的标题|第一行正文" in page.locator("#published").text_content()

    _with_page(html, assert_page)


def test_bilibili_publish_source_runs_inside_script_engine():
    source = Path("src/skill_library/send/bilibili_publish.py").read_text(
        encoding="utf-8"
    )
    urls = []
    engine = ScriptEngine()
    engine.register_functions(
        {
            "goto": lambda url: urls.append(url) or "ok",
            "run_js": _mock_publish_run_js("标题", "正文"),
            "wait": _noop,
            "get_url": lambda: "https://member.bilibili.com/platform/upload/text/new-article",
            "get_text": lambda: "",
        }
    )

    result = engine.execute(
        source + "\nresult = run('13574133406', '标题', '正文', max_wait_seconds=0)\nprint(result)"
    )

    assert result.success is True
    assert urls == ["https://member.bilibili.com/platform/upload/text/new-article"]
    assert "'success': True" in result.output
