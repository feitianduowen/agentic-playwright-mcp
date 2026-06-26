"""Tests for the Douyin SMS login skill adapter."""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from src.core.script_engine import ScriptEngine
from src.skill_library.others.douyin_login import (
    _click_get_code,
    _ensure_sms_login_mode,
    _fill_phone,
    _open_login_panel,
    run,
)


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


def test_douyin_login_requests_code_and_stops_for_manual_entry():
    js_calls = []

    def run_js(code):
        js_calls.append(code)
        return {"success": True}

    result = run(
        "13574133406",
        wait_seconds=0,
        goto_fn=_noop,
        run_js_fn=run_js,
        wait_fn=_noop,
        get_url_fn=lambda: "https://www.douyin.com/discover",
        get_text_fn=lambda: "请输入手机号 获取验证码 请输入验证码",
        log_fn=_noop,
    )

    assert result["success"] is True
    assert result["requires_manual_code"] is True
    assert result["phone_number"] == "13574133406"
    assert len(js_calls) == 5


def test_douyin_login_normalizes_china_country_code():
    result = run(
        "+86 135-7413-3406",
        wait_seconds=0,
        goto_fn=_noop,
        run_js_fn=lambda code: {"success": True},
        wait_fn=_noop,
        get_url_fn=lambda: "https://www.douyin.com/discover",
        get_text_fn=lambda: "",
        log_fn=_noop,
    )

    assert result["success"] is True
    assert result["phone_number"] == "13574133406"


def test_douyin_login_rejects_invalid_phone_number():
    result = run(
        "12345",
        wait_seconds=0,
        goto_fn=_noop,
        run_js_fn=lambda code: {"success": True},
        wait_fn=_noop,
        get_url_fn=lambda: "https://www.douyin.com/discover",
        get_text_fn=lambda: "",
        log_fn=_noop,
    )

    assert result["success"] is False
    assert "valid 11-digit phone number" in result["error"]


def test_douyin_login_reports_verification_page():
    result = run(
        "13574133406",
        wait_seconds=0,
        goto_fn=_noop,
        run_js_fn=lambda code: {"success": True},
        wait_fn=_noop,
        get_url_fn=lambda: "https://www.douyin.com/",
        get_text_fn=lambda: "验证码中间页",
        log_fn=_noop,
    )

    assert result["success"] is False
    assert result["requires_verification"] is True


def test_douyin_open_login_script_prefers_top_right_red_button():
    js_calls = []

    result = _open_login_panel(lambda code: js_calls.append(code) or {"success": True})

    assert result["success"] is True
    assert "#douyin-header button" in js_calls[0]
    assert "semi-button-primary" in js_calls[0]
    assert "top_right_login_button" in js_calls[0]


def test_douyin_open_login_clicks_top_right_red_button():
    html = """
    <body style="margin:0">
      <input id="search" placeholder="搜索" type="text"
        style="position:absolute;left:240px;top:16px;width:300px;height:34px" />
      <div id="wrong-login" role="button"
        style="position:absolute;left:24px;top:300px;width:80px;height:36px">登录</div>
      <div id="douyin-header"
        style="position:absolute;left:0;right:0;top:0;height:64px">
        <button id="real-login" class="semi-button semi-button-primary"
          style="position:absolute;right:24px;top:12px;width:72px;height:36px">
          登录
        </button>
      </div>
      <div id="clicked">none</div>
      <div id="login-panel-new" style="display:none">登录后免费畅享高清视频</div>
      <script>
        document.getElementById('wrong-login').addEventListener('click', () => {
          document.getElementById('clicked').textContent = 'wrong';
        });
        document.getElementById('real-login').addEventListener('click', () => {
          document.getElementById('clicked').textContent = 'top-right';
          document.getElementById('login-panel-new').style.display = 'block';
        });
      </script>
    </body>
    """

    def assert_page(page):
        result = _open_login_panel(lambda code: page.evaluate(code))

        assert result["success"] is True
        assert result["method"] == "top_right_login_button"
        assert page.locator("#clicked").text_content() == "top-right"

    _with_page(html, assert_page)


def test_douyin_open_login_retries_until_popup_marker_appears():
    html = """
    <body style="margin:0">
      <div id="douyin-header"
        style="position:absolute;left:0;right:0;top:0;height:64px">
        <button id="real-login" class="semi-button semi-button-primary"
          style="position:absolute;right:24px;top:12px;width:72px;height:36px">
          登录
        </button>
      </div>
      <div id="login-panel-new" style="display:none;margin-top:80px">
        <div>登录后免费畅享高清视频</div>
      </div>
      <div id="click-count">0</div>
      <script>
        document.getElementById('real-login').addEventListener('click', () => {
          const count = Number(document.getElementById('click-count').textContent) + 1;
          document.getElementById('click-count').textContent = String(count);
          if (count >= 2) {
            document.getElementById('login-panel-new').style.display = 'block';
          }
        });
      </script>
    </body>
    """

    def assert_page(page):
        result = _open_login_panel(lambda code: page.evaluate(code))

        assert result["success"] is True
        assert result["marker_found"] is True
        assert result["attempts"] == 2
        assert page.locator("#click-count").text_content() == "2"

    _with_page(html, assert_page)


def test_douyin_fill_phone_does_not_use_search_input_without_login_panel():
    html = """
    <body>
      <input id="search" placeholder="搜索" type="text"
        style="width:300px;height:34px" />
    </body>
    """

    def assert_page(page):
        result = _fill_phone(lambda code: page.evaluate(code), "13574133406")

        assert result["success"] is False
        assert "login panel" in result["error"]
        assert page.locator("#search").input_value() == ""

    _with_page(html, assert_page)


def test_douyin_fill_phone_targets_login_panel_phone_input():
    html = """
    <body>
      <input id="search" placeholder="搜索" type="text"
        style="width:300px;height:34px" />
      <div id="login-panel-new">
        <input id="normal-input" name="normal-input" type="tel"
          placeholder="请输入手机号" style="width:300px;height:34px" />
      </div>
    </body>
    """

    def assert_page(page):
        result = _fill_phone(lambda code: page.evaluate(code), "13574133406")

        assert result["success"] is True
        assert page.locator("#normal-input").input_value() == "13574133406"
        assert page.locator("#search").input_value() == ""

    _with_page(html, assert_page)


def test_douyin_ensure_sms_login_mode_clicks_sms_switch():
    html = """
    <body>
      <div id="login-panel-new">
        <div id="switch" role="button">验证码登录</div>
        <script>
          document.getElementById('switch').addEventListener('click', () => {
            const input = document.createElement('input');
            input.id = 'normal-input';
            input.name = 'normal-input';
            input.type = 'tel';
            input.placeholder = '请输入手机号';
            document.getElementById('login-panel-new').appendChild(input);
          });
        </script>
      </div>
    </body>
    """

    def assert_page(page):
        result = _ensure_sms_login_mode(lambda code: page.evaluate(code))

        assert result["success"] is True
        assert result["method"] == "sms_login_mode_switch"
        assert page.locator("#normal-input").is_visible()

    _with_page(html, assert_page)


def test_douyin_phone_typing_enables_and_clicks_get_code_button():
    html = """
    <body>
      <input id="search" placeholder="搜索" type="text" />
      <div id="login-panel-new">
        <input id="normal-input" name="normal-input" type="tel"
          placeholder="请输入手机号" />
        <input id="button-input" name="button-input" type="text"
          placeholder="请输入验证码" />
        <button id="douyin_login_comp_button_input_id" disabled>获取验证码</button>
      </div>
      <div id="input-count">0</div>
      <div id="code-clicked">no</div>
      <script>
        const phone = document.getElementById('normal-input');
        const button = document.getElementById('douyin_login_comp_button_input_id');
        phone.addEventListener('input', () => {
          const count = Number(document.getElementById('input-count').textContent) + 1;
          document.getElementById('input-count').textContent = String(count);
          if (phone.value.replace(/\\D/g, '').length >= 11) {
            button.disabled = false;
          }
        });
        button.addEventListener('click', () => {
          document.getElementById('code-clicked').textContent = 'yes';
        });
      </script>
    </body>
    """

    def assert_page(page):
        fill_result = _fill_phone(lambda code: page.evaluate(code), "13574133406")
        click_result = _click_get_code(lambda code: page.evaluate(code))

        assert fill_result["success"] is True
        assert page.locator("#normal-input").input_value() == "13574133406"
        assert int(page.locator("#input-count").text_content()) >= 11
        assert click_result["success"] is True
        assert page.locator("#code-clicked").text_content() == "yes"
        assert page.locator("#search").input_value() == ""

    _with_page(html, assert_page)


def test_douyin_clicks_red_send_code_text_below_phone_input():
    html = """
    <body>
      <div id="login-panel-new">
        <input id="normal-input" name="normal-input" type="tel"
          placeholder="请输入手机号" value="135 7413 3406" />
        <div style="margin-top:10px">
          <span id="send-code" style="color: rgb(254, 44, 85); cursor: pointer">
            发送验证码
          </span>
        </div>
      </div>
      <div id="code-clicked">no</div>
      <script>
        document.getElementById('send-code').addEventListener('click', () => {
          document.getElementById('code-clicked').textContent = 'yes';
        });
      </script>
    </body>
    """

    def assert_page(page):
        result = _click_get_code(lambda code: page.evaluate(code))

        assert result["success"] is True
        assert result["method"] == "phone_input_below_red_text"
        assert result["below_phone_input"] is True
        assert result["red_text"] is True
        assert page.locator("#code-clicked").text_content() == "yes"

    _with_page(html, assert_page)


def test_douyin_run_opens_fills_and_clicks_code_in_page_flow():
    html = """
    <body style="margin:0">
      <input id="search" placeholder="搜索" type="text"
        style="position:absolute;left:240px;top:16px;width:300px;height:34px" />
      <div id="douyin-header"
        style="position:absolute;left:0;right:0;top:0;height:64px">
        <button id="real-login" class="semi-button semi-button-primary"
          style="position:absolute;right:24px;top:12px;width:72px;height:36px">
          登录
        </button>
      </div>
      <div id="login-panel-new" style="display:none;margin-top:80px">
        <div>登录后免费畅享高清视频</div>
        <input id="normal-input" name="normal-input" type="tel"
          placeholder="请输入手机号" />
        <input id="button-input" name="button-input" type="text"
          placeholder="请输入验证码" />
        <button id="douyin_login_comp_button_input_id" disabled>获取验证码</button>
      </div>
      <div id="code-clicked">no</div>
      <script>
        document.getElementById('real-login').addEventListener('click', () => {
          document.getElementById('login-panel-new').style.display = 'block';
        });
        const phone = document.getElementById('normal-input');
        const button = document.getElementById('douyin_login_comp_button_input_id');
        phone.addEventListener('input', () => {
          if (phone.value.replace(/\\D/g, '').length >= 11) {
            button.disabled = false;
          }
        });
        button.addEventListener('click', () => {
          document.getElementById('code-clicked').textContent = 'yes';
        });
      </script>
    </body>
    """

    def assert_page(page):
        result = run(
            "13574133406",
            wait_seconds=0,
            goto_fn=lambda url: "ok",
            run_js_fn=lambda code: page.evaluate(code),
            wait_fn=lambda seconds: page.wait_for_timeout(int(seconds * 1000)) or "ok",
            get_url_fn=lambda: "https://www.douyin.com/discover",
            get_text_fn=lambda: page.locator("body").inner_text(),
            log_fn=_noop,
        )

        assert result["success"] is True
        assert result["requires_manual_code"] is True
        assert page.locator("#normal-input").input_value() == "13574133406"
        assert page.locator("#code-clicked").text_content() == "yes"
        assert page.locator("#search").input_value() == ""

    _with_page(html, assert_page)


def test_douyin_get_code_script_prefers_code_input_row():
    js_calls = []

    result = _click_get_code(lambda code: js_calls.append(code) or {"success": True})

    assert result["success"] is True
    assert "codeInput" in js_calls[0]
    assert "sameRow" in js_calls[0]
    assert "rightOfCodeInput" in js_calls[0]
    assert "douyin_login_comp_button_input_id" in js_calls[0]


def test_douyin_login_source_runs_inside_script_engine():
    source = Path("src/skill_library/others/douyin_login.py").read_text(
        encoding="utf-8"
    )
    engine = ScriptEngine()
    engine.register_functions(
        {
            "goto": _noop,
            "run_js": lambda code: {"success": True},
            "wait": _noop,
            "get_url": lambda: "https://www.douyin.com/discover",
            "get_text": lambda: "请输入手机号 获取验证码 请输入验证码",
        }
    )

    result = engine.execute(
        source + "\nresult = run('13574133406', wait_seconds=0)\nprint(result)"
    )

    assert result.success is True
    assert "'requires_manual_code': True" in result.output
