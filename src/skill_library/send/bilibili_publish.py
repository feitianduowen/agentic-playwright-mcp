"""Bilibili article publishing adapter."""

try:
    from src.layer_2 import controls as _controls
except Exception:
    _controls = None


DEFAULT_LOGIN_URL = "https://www.bilibili.com"
DEFAULT_UPLOAD_URL = "https://member.bilibili.com/platform/upload/text/new-article"
FALLBACK_UPLOAD_URL = "https://member.bilibili.com/platform/upload/text/new-edit"


def _default_log(message):
    print(f"[LOG] {message}")


def _resolve_log(log_fn):
    if log_fn is not None:
        return log_fn
    try:
        return log
    except NameError:
        return _default_log


def _safe_call(func, default, *args):
    try:
        return func(*args)
    except Exception:
        return default


def _normalize_phone_number(phone_number):
    digits = ""
    for char in str(phone_number):
        if "0" <= char <= "9":
            digits += char

    if len(digits) == 13 and digits[:2] == "86":
        digits = digits[2:]

    if len(digits) != 11 or digits[0] != "1" or digits[1] < "3" or digits[1] > "9":
        raise ValueError("Bilibili publish requires a valid 11-digit phone number")

    return digits


def _js_string(value):
    text = str(value)
    text = text.replace("\\", "\\\\")
    text = text.replace('"', '\\"')
    text = text.replace("\n", "\\n")
    text = text.replace("\r", "\\r")
    return '"' + text + '"'


def _run_js_dict(run_js_fn, code):
    try:
        result = run_js_fn(code)
    except Exception as exc:
        return {"success": False, "error": f"{type(exc).__name__}: {exc}"}

    if isinstance(result, dict):
        return result
    return {"success": bool(result), "result": result}


def _detect_login_state(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const loginPopup = Array.from(document.querySelectorAll(
    '.bili-mini-login,.login-panel,[class*="login-panel" i],[class*="mini-login" i],[class*="login"]'
  )).some((el) => visible(el) && (
    compactText(el).includes('\\u77ed\\u4fe1\\u767b\\u5f55') ||
    compactText(el).includes('\\u9a8c\\u8bc1\\u7801') ||
    compactText(el).includes('\\u767b\\u5f55\\u6216\\u5b8c\\u6210\\u6ce8\\u518c')
  ));
  const loginEntry = Array.from(document.querySelectorAll(
    '.header-login-entry,[class*="login-entry"],button,[role="button"],a,div,span'
  )).some((el) => {
    const rect = el.getBoundingClientRect();
    const topRight = rect.top < Math.max(180, window.innerHeight * 0.3) &&
      rect.left > window.innerWidth * 0.45;
    return visible(el) && topRight && compactText(el) === '\\u767b\\u5f55';
  });
  const avatar = Array.from(document.querySelectorAll(
    '.header-avatar,.bili-avatar,.b-avatar,[class*="avatar" i],.right-entry__outside img,.right-entry img'
  )).some((el) => visible(el));
  const memberPage = location.hostname.includes('member.bilibili.com');
  const loggedIn = (avatar && !loginPopup) || (memberPage && !loginEntry && !loginPopup);
  return {
    success: true,
    logged_in: loggedIn,
    login_popup: loginPopup,
    login_entry: loginEntry,
    avatar: avatar,
    url: location.href
  };
})()
""",
    )


def _open_login_panel(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(async () => {
  const LOGIN_TEXT = '\\u767b\\u5f55';
  const SMS_LOGIN_TEXT = '\\u77ed\\u4fe1\\u767b\\u5f55';
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const hasSmsLogin = () => Array.from(document.querySelectorAll('body,button,[role="button"],a,div,span,p'))
    .some((el) => visible(el) && compactText(el).includes(SMS_LOGIN_TEXT));
  if (hasSmsLogin()) {
    return {success: true, already_open: true, marker_found: true};
  }
  const score = (el) => {
    const rect = el.getBoundingClientRect();
    const className = String(el.className || '');
    let value = 0;
    if (/header-login-entry/i.test(className)) value -= 3000;
    if (/login-entry/i.test(className)) value -= 1500;
    if (rect.top < Math.max(180, window.innerHeight * 0.3) &&
        rect.left > window.innerWidth * 0.45) value -= 900;
    value += rect.top;
    value -= rect.left / 10;
    return value;
  };
  const findButton = () => {
    const nodes = Array.from(document.querySelectorAll(
      '.header-login-entry,.right-entry__outside .header-login-entry,[class*="login-entry"],button,[role="button"],a,div,span'
    )).filter(visible).filter((el) => {
      const label = [
        compactText(el),
        el.getAttribute('aria-label') || '',
        el.getAttribute('title') || ''
      ].join('').trim().replace(/\\s+/g, '');
      const rect = el.getBoundingClientRect();
      const topRight = rect.top < Math.max(180, window.innerHeight * 0.3) &&
        rect.left > window.innerWidth * 0.45;
      return label === LOGIN_TEXT && (topRight || /login/i.test(String(el.className || '')));
    });
    nodes.sort((a, b) => score(a) - score(b));
    return nodes[0] || null;
  };
  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  for (let attempt = 1; attempt <= 6; attempt += 1) {
    const button = findButton();
    if (!button) {
      return {success: false, error: 'Bilibili login icon not found', attempts: attempt - 1};
    }
    const target = button.closest('button,[role="button"],a') || button;
    target.scrollIntoView({block: 'center', inline: 'center'});
    target.click();
    await pause(700);
    if (hasSmsLogin()) {
      return {success: true, clicked: true, marker_found: true, attempts: attempt};
    }
  }
  return {success: false, error: 'Bilibili SMS login marker not found', attempts: 6};
})()
""",
    )


def _click_sms_login(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(async () => {
  const SMS_LOGIN_TEXT = '\\u77ed\\u4fe1\\u767b\\u5f55';
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const hasPhoneInput = () => Array.from(document.querySelectorAll('input')).some((el) => {
    const text = [el.placeholder || '', el.type || '', el.name || '', el.id || ''].join(' ').toLowerCase();
    return visible(el) && /(手机号|手机|phone|mobile|tel)/i.test(text);
  });
  if (hasPhoneInput()) {
    return {success: true, already_sms_mode: true};
  }
  const candidates = Array.from(document.querySelectorAll('button,[role="button"],a,div,span,p,li'))
    .filter(visible).map((el) => {
      const rect = el.getBoundingClientRect();
      const text = compactText(el);
      return {el, rect, text, clickable: Boolean(el.closest('button,[role="button"],a'))};
    }).filter((item) => item.text.includes(SMS_LOGIN_TEXT) &&
      (item.text === SMS_LOGIN_TEXT || item.text.length <= 16 || item.clickable));
  if (!candidates.length) {
    return {success: false, error: 'SMS login switch not found'};
  }
  candidates.sort((a, b) => (a.rect.width * a.rect.height) - (b.rect.width * b.rect.height));
  const target = candidates[0].el.closest('button,[role="button"],a') || candidates[0].el;
  target.scrollIntoView({block: 'center', inline: 'center'});
  target.click();
  await new Promise((resolve) => setTimeout(resolve, 400));
  return {success: true, clicked: true, has_phone_input_after: hasPhoneInput()};
})()
""",
    )


def _fill_login_phone(run_js_fn, phone_number):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const phone = PHONE_NUMBER;
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const textOf = (el) => [
    el.placeholder || '',
    el.type || '',
    el.name || '',
    el.id || '',
    el.autocomplete || '',
    el.inputMode || '',
    el.getAttribute('aria-label') || ''
  ].join(' ').toLowerCase();
  const inLoginArea = (el) => {
    let node = el;
    for (let i = 0; i < 7 && node; i += 1) {
      const text = compactText(node);
      if (text.includes('\\u77ed\\u4fe1\\u767b\\u5f55') || text.includes('\\u9a8c\\u8bc1\\u7801')) {
        return true;
      }
      node = node.parentElement;
    }
    return false;
  };
  const target = Array.from(document.querySelectorAll('input')).filter(visible).find((el) => {
    const text = textOf(el);
    return inLoginArea(el) && /(手机号|手机|phone|mobile|tel)/i.test(text) &&
      !/(验证码|code|密码|password|搜索|search|账号|account)/i.test(text);
  });
  if (!target) {
    return {success: false, error: 'Phone input not found'};
  }
  const descriptor = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
  target.scrollIntoView({block: 'center', inline: 'center'});
  target.focus();
  if (descriptor && descriptor.set) {
    descriptor.set.call(target, phone);
  } else {
    target.value = phone;
  }
  target.dispatchEvent(new Event('input', {bubbles: true}));
  target.dispatchEvent(new Event('change', {bubbles: true}));
  return {success: (target.value || '').replace(/\\D/g, '') === phone, value: target.value || ''};
})()
""".replace("PHONE_NUMBER", _js_string(phone_number)),
    )


def _click_get_code(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const SEND_TEXT = '\\u53d1\\u9001\\u9a8c\\u8bc1\\u7801';
  const GET_TEXT = '\\u83b7\\u53d6\\u9a8c\\u8bc1\\u7801';
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const nodes = Array.from(document.querySelectorAll('button,[role="button"],a,div,span,p'))
    .filter(visible).map((el) => ({el, text: compactText(el), rect: el.getBoundingClientRect()}))
    .filter((item) => {
      if (/收不到|语音|无法/.test(item.text)) return false;
      return item.text === SEND_TEXT || item.text === GET_TEXT ||
        (item.text.includes(SEND_TEXT) && item.text.length <= 24) ||
        (item.text.includes(GET_TEXT) && item.text.length <= 24);
    });
  if (!nodes.length) {
    return {success: false, error: 'Get-code button not found'};
  }
  nodes.sort((a, b) => {
    const score = (item) => {
      let value = item.rect.width * item.rect.height / 1000;
      if (item.text === SEND_TEXT) value -= 140;
      if (item.text === GET_TEXT) value -= 80;
      return value;
    };
    return score(a) - score(b);
  });
  const target = nodes[0].el.closest('button,[role="button"],a') || nodes[0].el;
  if (target.disabled || target.getAttribute('aria-disabled') === 'true') {
    return {success: false, error: 'Get-code button is disabled', text: nodes[0].text};
  }
  target.scrollIntoView({block: 'center', inline: 'center'});
  target.click();
  return {success: true, text: nodes[0].text};
})()
""",
    )


def _prepare_sms_login(phone, goto_fn, run_js_fn, wait_fn, get_url_fn, get_text_fn, steps):
    state = _detect_login_state(run_js_fn)
    steps.append({"step": "detect_login_state", "result": state})
    if state.get("logged_in"):
        return {"success": True, "already_logged_in": True}

    steps.append({"step": "navigate_login", "result": goto_fn(DEFAULT_LOGIN_URL)})
    steps.append({"step": "wait_after_login_navigation", "result": _safe_call(wait_fn, "", 1)})

    open_result = _open_login_panel(run_js_fn)
    steps.append({"step": "open_login_panel", "result": open_result})
    if not open_result.get("success"):
        return {"success": False, "error": "Failed to open Bilibili login panel"}

    sms_result = _click_sms_login(run_js_fn)
    steps.append({"step": "click_sms_login", "result": sms_result})
    if not sms_result.get("success"):
        return {"success": False, "error": "Failed to switch to SMS login"}

    fill_result = _fill_login_phone(run_js_fn, phone)
    steps.append({"step": "fill_login_phone", "result": fill_result})
    if not fill_result.get("success"):
        return {"success": False, "error": "Failed to fill Bilibili login phone"}

    get_code_result = _click_get_code(run_js_fn)
    steps.append({"step": "click_get_code", "result": get_code_result})
    if not get_code_result.get("success"):
        return {"success": False, "error": "Failed to request Bilibili verification code"}

    return {
        "success": True,
        "requires_manual_verification": True,
        "requires_manual_code": True,
        "url": _safe_call(get_url_fn, ""),
        "text": _safe_call(get_text_fn, ""),
    }


def _wait_for_login_completion(run_js_fn, wait_fn, steps, max_wait_seconds, interval_seconds):
    attempts = max(1, int(max_wait_seconds / interval_seconds) + 1)
    for attempt in range(1, attempts + 1):
        state = _detect_login_state(run_js_fn)
        steps.append({"step": f"wait_login_completion_attempt_{attempt}", "result": state})
        if state.get("logged_in"):
            return {"success": True, "attempts": attempt, "state": state}
        if attempt < attempts:
            steps.append(
                {
                    "step": f"wait_before_login_completion_attempt_{attempt + 1}",
                    "result": _safe_call(wait_fn, "", interval_seconds),
                }
            )
    return {
        "success": False,
        "requires_manual_login": True,
        "error": "Timed out waiting for Bilibili manual verification/login completion",
    }


def _editor_ready(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const hasTitle = Array.from(document.querySelectorAll('input,textarea,[contenteditable="true"],div,span'))
    .some((el) => visible(el) && /标题|title/i.test([
      el.placeholder || '',
      el.getAttribute('aria-label') || '',
      el.getAttribute('data-placeholder') || '',
      el.className || '',
      el.id || ''
    ].join(' ')));
  const hasEditor = Array.from(document.querySelectorAll('[contenteditable="true"],textarea,.ql-editor,.ProseMirror,[class*="editor" i]'))
    .some((el) => visible(el));
  return {success: true, ready: hasTitle && hasEditor};
})()
""",
    )


def _set_editable(el_var, value_var):
    return f"""
  {{
  const setEditable = (el, value) => {{
    el.scrollIntoView({{block: 'center', inline: 'center'}});
    el.focus();
    if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {{
      const proto = el.tagName === 'TEXTAREA' ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
      const descriptor = Object.getOwnPropertyDescriptor(proto, 'value');
      if (descriptor && descriptor.set) {{
        descriptor.set.call(el, value);
      }} else {{
        el.value = value;
      }}
    }} else {{
      const escapeHtml = (text) => String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
      el.innerHTML = String(value).split('\\n').map((line) => escapeHtml(line) || '<br>').join('<br>');
    }}
    try {{
      el.dispatchEvent(new InputEvent('beforeinput', {{
        bubbles: true,
        cancelable: true,
        inputType: 'insertText',
        data: value
      }}));
    }} catch (error) {{}}
    try {{
      el.dispatchEvent(new InputEvent('input', {{
        bubbles: true,
        cancelable: true,
        inputType: 'insertText',
        data: value
      }}));
    }} catch (error) {{
      el.dispatchEvent(new Event('input', {{bubbles: true}}));
    }}
    el.dispatchEvent(new Event('change', {{bubbles: true}}));
    el.dispatchEvent(new Event('blur', {{bubbles: true}}));
  }};
  setEditable({el_var}, {value_var});
  }}
"""


def _fill_article(run_js_fn, title, body):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const title = TITLE_TEXT;
  const body = BODY_TEXT;
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const labelOf = (el) => [
    el.placeholder || '',
    el.getAttribute('aria-label') || '',
    el.getAttribute('data-placeholder') || '',
    el.getAttribute('title') || '',
    el.name || '',
    el.id || '',
    String(el.className || '')
  ].join(' ').toLowerCase();
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const denied = (text) => /(搜索|search|验证码|密码|手机号|phone|mobile|login|上传封面|tag|标签)/i.test(text);
  const titleCandidates = Array.from(document.querySelectorAll(
    'input,textarea,[contenteditable="true"],[role="textbox"]'
  )).filter(visible).map((el) => {
    const rect = el.getBoundingClientRect();
    const label = labelOf(el);
    const nearText = compactText(el.parentElement || el);
    return {el, rect, label, nearText};
  }).filter((item) => {
    if (denied(item.label)) return false;
    return /标题|title/.test(item.label) ||
      /标题/.test(item.nearText) ||
      /title/i.test(String(item.el.className || item.el.id || ''));
  });
  titleCandidates.sort((a, b) => {
    const score = (item) => {
      let value = item.rect.top;
      if (/标题|title/.test(item.label)) value -= 1000;
      if (item.el.tagName === 'INPUT' || item.el.tagName === 'TEXTAREA') value -= 300;
      if (/title/i.test(String(item.el.className || ''))) value -= 200;
      return value;
    };
    return score(a) - score(b);
  });
  const titleEl = titleCandidates[0] ? titleCandidates[0].el : null;
  if (!titleEl) {
    return {success: false, error: 'Bilibili article title input not found'};
  }

  const bodyCandidates = Array.from(document.querySelectorAll(
    '[contenteditable="true"],textarea,.ql-editor,.ProseMirror,[role="textbox"],[class*="editor" i]'
  )).filter(visible).filter((el) => el !== titleEl).map((el) => {
    const rect = el.getBoundingClientRect();
    const label = labelOf(el);
    const nearText = compactText(el.parentElement || el);
    return {el, rect, label, nearText};
  }).filter((item) => {
    if (denied(item.label)) return false;
    if (/标题|title/.test(item.label) && item.rect.height < 120) return false;
    return /正文|内容|文章|editor|content|body|请输入正文|写点什么/i.test(item.label + item.nearText) ||
      item.rect.height >= 120 ||
      item.el.isContentEditable;
  });
  bodyCandidates.sort((a, b) => {
    const score = (item) => {
      let value = 0;
      if (item.el.isContentEditable) value -= 500;
      if (/ql-editor|ProseMirror|editor/i.test(String(item.el.className || ''))) value -= 400;
      if (/正文|内容|文章|content|body/.test(item.label + item.nearText)) value -= 300;
      value -= Math.min(item.rect.height, 500) / 5;
      value += Math.abs(item.rect.top - titleEl.getBoundingClientRect().bottom) / 20;
      return value;
    };
    return score(a) - score(b);
  });
  const bodyEl = bodyCandidates[0] ? bodyCandidates[0].el : null;
  if (!bodyEl) {
    return {success: false, error: 'Bilibili article body editor not found'};
  }

SET_EDITABLE_TITLE
SET_EDITABLE_BODY

  const titleValue = titleEl.value || titleEl.innerText || titleEl.textContent || '';
  const bodyValue = bodyEl.value || bodyEl.innerText || bodyEl.textContent || '';
  return {
    success: titleValue.includes(title) && bodyValue.includes(body.split('\\n')[0]),
    title_value: titleValue,
    body_value: bodyValue,
    title_selector: titleEl.placeholder || titleEl.className || titleEl.id || titleEl.tagName,
    body_selector: bodyEl.getAttribute('data-placeholder') || bodyEl.className || bodyEl.id || bodyEl.tagName
  };
})()
"""
        .replace("TITLE_TEXT", _js_string(title))
        .replace("BODY_TEXT", _js_string(body))
        .replace("SET_EDITABLE_TITLE", _set_editable("titleEl", "title"))
        .replace("SET_EDITABLE_BODY", _set_editable("bodyEl", "body")),
    )


def _click_publish(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const PUBLISH_TEXT = '\\u53d1\\u5e03';
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const nodes = Array.from(document.querySelectorAll('button,[role="button"],a,div,span'))
    .filter(visible).map((el) => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      const text = compactText(el);
      const bottomRight = rect.top > window.innerHeight * 0.45 && rect.left > window.innerWidth * 0.45;
      const blue = /rgb\\(\\s*(0|20|30|64)\\s*,\\s*(1[4-9][0-9]|2[0-5][0-9])\\s*,\\s*(2[0-5][0-9])\\s*\\)|#?00a1d6|#?00aeec|#?1890ff/i.test(
        `${style.backgroundColor} ${style.color} ${style.borderColor}`
      );
      const clickable = Boolean(el.closest('button,[role="button"],a')) || el.tagName === 'BUTTON';
      return {el, rect, text, bottomRight, blue, clickable};
    }).filter((item) => {
      if (!item.text.includes(PUBLISH_TEXT)) return false;
      if (/定时|设置|声明|转载|发布设置/.test(item.text)) return false;
      return item.text === PUBLISH_TEXT || item.text.length <= 12 || (item.bottomRight && item.blue);
    });
  if (!nodes.length) {
    return {success: false, error: 'Bilibili publish button not found'};
  }
  nodes.sort((a, b) => {
    const score = (item) => {
      let value = item.rect.width * item.rect.height / 1000;
      if (item.text === PUBLISH_TEXT) value -= 500;
      if (item.bottomRight) value -= 300;
      if (item.blue) value -= 200;
      if (item.clickable) value -= 100;
      return value;
    };
    return score(a) - score(b);
  });
  const target = nodes[0].el.closest('button,[role="button"],a') || nodes[0].el;
  if (target.disabled || target.getAttribute('aria-disabled') === 'true') {
    return {success: false, error: 'Bilibili publish button is disabled', text: nodes[0].text};
  }
  target.scrollIntoView({block: 'center', inline: 'center'});
  target.click();
  return {
    success: true,
    text: nodes[0].text,
    method: nodes[0].bottomRight ? 'bottom_right_publish_button' : 'publish_button',
    blue: Boolean(nodes[0].blue)
  };
})()
""",
    )


def _retry(step_name, action_fn, steps, wait_fn, attempts, interval):
    result = {"success": False, "error": "step not attempted"}
    for attempt in range(1, attempts + 1):
        result = action_fn()
        suffix = "" if attempt == 1 else f"_attempt_{attempt}"
        steps.append({"step": f"{step_name}{suffix}", "result": result})
        if result.get("success"):
            return result
        if attempt < attempts:
            steps.append(
                {
                    "step": f"wait_before_{step_name}_attempt_{attempt + 1}",
                    "result": _safe_call(wait_fn, "", interval),
                }
            )
    return result


def run(
    phone_number,
    title,
    body,
    *,
    upload_url=DEFAULT_UPLOAD_URL,
    max_wait_seconds=300,
    goto_fn=None,
    run_js_fn=None,
    wait_fn=None,
    get_url_fn=None,
    get_text_fn=None,
    log_fn=None,
):
    """Log in to Bilibili, open article editor, fill title/body, and publish."""
    if goto_fn is None:
        goto_fn = _controls.goto if _controls is not None else goto
    if run_js_fn is None:
        run_js_fn = _controls.run_js if _controls is not None else run_js
    if wait_fn is None:
        wait_fn = _controls.wait if _controls is not None else wait
    if get_url_fn is None:
        get_url_fn = _controls.get_page_url if _controls is not None else get_url
    if get_text_fn is None:
        get_text_fn = _controls.get_page_text if _controls is not None else get_text

    log_fn = _resolve_log(log_fn)
    steps = []

    try:
        phone = _normalize_phone_number(phone_number)
        article_title = str(title).strip()
        article_body = str(body).strip()
        if not article_title:
            raise ValueError("Bilibili publish requires title")
        if not article_body:
            raise ValueError("Bilibili publish requires body")

        login_result = _prepare_sms_login(
            phone,
            goto_fn,
            run_js_fn,
            wait_fn,
            get_url_fn,
            get_text_fn,
            steps,
        )
        steps.append({"step": "prepare_sms_login", "result": login_result})
        if not login_result.get("success"):
            return {
                "success": False,
                "error": login_result.get("error", "Failed to prepare Bilibili SMS login"),
                "steps": steps,
            }

        if not login_result.get("already_logged_in"):
            log_fn("Please complete Bilibili human verification and SMS login in the browser.")
            wait_result = _wait_for_login_completion(
                run_js_fn,
                wait_fn,
                steps,
                max_wait_seconds=max_wait_seconds,
                interval_seconds=2,
            )
            steps.append({"step": "manual_login_completion", "result": wait_result})
            if not wait_result.get("success"):
                return {
                    "success": False,
                    "requires_manual_login": True,
                    "error": "Please complete Bilibili human verification/login before publishing",
                    "steps": steps,
                }

        steps.append({"step": "navigate_upload_editor", "result": goto_fn(upload_url)})
        steps.append({"step": "wait_after_upload_navigation", "result": _safe_call(wait_fn, "", 2)})
        editor_ready = _editor_ready(run_js_fn)
        steps.append({"step": "editor_ready", "result": editor_ready})

        if not editor_ready.get("ready") and upload_url != FALLBACK_UPLOAD_URL:
            steps.append(
                {"step": "navigate_upload_editor_fallback", "result": goto_fn(FALLBACK_UPLOAD_URL)}
            )
            steps.append(
                {"step": "wait_after_upload_fallback", "result": _safe_call(wait_fn, "", 2)}
            )

        fill_result = _retry(
            "fill_article",
            lambda: _fill_article(run_js_fn, article_title, article_body),
            steps,
            wait_fn,
            attempts=5,
            interval=1,
        )
        if not fill_result.get("success"):
            return {
                "success": False,
                "error": "Failed to fill Bilibili article title/body",
                "steps": steps,
            }

        publish_result = _retry(
            "click_publish",
            lambda: _click_publish(run_js_fn),
            steps,
            wait_fn,
            attempts=5,
            interval=1,
        )
        if not publish_result.get("success"):
            return {
                "success": False,
                "error": "Failed to click Bilibili publish button",
                "steps": steps,
            }

        log_fn("Bilibili article publish button clicked")
        return {
            "success": True,
            "title": article_title,
            "body": article_body,
            "url": _safe_call(get_url_fn, ""),
            "steps": steps,
            "message": "Bilibili article title/body filled and publish button clicked.",
        }

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        log_fn(f"Bilibili article publish failed: {error}")
        return {"success": False, "error": error, "steps": steps}
