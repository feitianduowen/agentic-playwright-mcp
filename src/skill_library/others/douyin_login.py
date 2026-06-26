"""Douyin SMS login preparation.

The skill opens Douyin, fills a phone number, and requests an SMS code.
The final code entry remains manual.
"""

try:
    from src.layer_2 import controls as _controls
except Exception:
    _controls = None


DEFAULT_LOGIN_URL = "https://www.douyin.com/discover"


def _default_log(message):
    print(f"[LOG] {message}")


def _safe_call(func, default, *args):
    try:
        return func(*args)
    except Exception:
        return default


def _resolve_log(log_fn):
    if log_fn is not None:
        return log_fn
    try:
        return log
    except NameError:
        return _default_log


def _normalize_phone_number(phone_number):
    digits = ""
    for char in str(phone_number):
        if "0" <= char <= "9":
            digits += char

    if len(digits) == 13 and digits[:2] == "86":
        digits = digits[2:]

    if len(digits) != 11 or digits[0] != "1" or digits[1] < "3" or digits[1] > "9":
        raise ValueError("Douyin login requires a valid 11-digit phone number")

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


def _detect_blocked(get_url_fn, get_text_fn):
    url = str(_safe_call(get_url_fn, "") or "")
    text = str(_safe_call(get_text_fn, "") or "")

    if (
        "验证码中间页" in text
        or "安全验证" in text
        or "captcha" in url.lower()
        or "captcha" in text.lower()
    ):
        return {
            "success": False,
            "requires_verification": True,
            "error": "Douyin requires extra verification before login",
            "url": url,
        }

    return None


def _open_login_panel(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(async () => {
  const LOGIN_TEXT = '\\u767b\\u5f55';
  const POPUP_MARKER = '\\u767b\\u5f55\\u540e\\u514d\\u8d39\\u7545\\u4eab\\u9ad8\\u6e05\\u89c6\\u9891';
  const PANEL_SELECTOR = [
    '#login-panel-new',
    '#douyin-login-new-id',
    '[id*="login-panel" i]',
    '[class*="login-panel" i]',
    '[id*="douyin-login" i]',
    '[class*="douyin-login" i]'
  ].join(',');
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const textOf = (el) => [
    el.placeholder || '',
    el.type || '',
    el.name || '',
    el.id || '',
    el.autocomplete || '',
    el.getAttribute('aria-label') || ''
  ].join(' ').toLowerCase();
  const inLoginPanel = (el) => {
    return Boolean(el.closest(PANEL_SELECTOR)) ||
      el.id === 'normal-input' || el.name === 'normal-input';
  };
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const markerVisible = () => {
    return Array.from(document.querySelectorAll('body,' + PANEL_SELECTOR)).some((el) => {
      return visible(el) && compactText(el).includes(POPUP_MARKER);
    });
  };
  const hasPhoneInput = Array.from(document.querySelectorAll('input')).some((el) => {
    return visible(el) && inLoginPanel(el) &&
      /(请输入手机号|手机号|手机|phone|mobile|tel|normal-input)/i.test(textOf(el));
  });
  if (markerVisible()) {
    return {
      success: true,
      already_open: true,
      marker_found: true,
      has_phone_input: hasPhoneInput
    };
  }

  const text = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const isLoginText = (el) => {
    const label = [
      text(el),
      el.getAttribute('aria-label') || '',
      el.getAttribute('title') || ''
    ].join('').trim().replace(/\\s+/g, '');
    return label === LOGIN_TEXT;
  };
  const clickElement = (el) => {
    const target = el.closest('button,[role="button"],a') || el;
    target.scrollIntoView({block: 'center', inline: 'center'});
    target.click();
    return target;
  };
  const rectScore = (el) => {
    const rect = el.getBoundingClientRect();
    const topRight = rect.top < Math.max(160, window.innerHeight * 0.25) &&
      rect.left > window.innerWidth * 0.45;
    const primary = /semi-button-primary|primary|red|login/i.test(el.className || '');
    let value = 0;
    if (el.tagName === 'BUTTON') {
      value -= 1000;
    }
    if (primary) {
      value -= 1000;
    }
    if (topRight) {
      value -= 800;
    }
    value += Math.max(0, rect.top);
    value -= Math.max(0, rect.left / 10);
    return value;
  };

  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const findHeaderButton = () => {
    const headerButtons = Array.from(
      document.querySelectorAll(
        '#douyin-header button,' +
        '#douyin-header [role="button"],' +
        '#douyin-header-menuCt button,' +
        '#douyin-header-menuCt [role="button"],' +
        '#douyin-right-container button,' +
        '#douyin-right-container [role="button"],' +
        'button.semi-button-primary'
      )
    ).filter(visible).filter(isLoginText);
    headerButtons.sort((a, b) => rectScore(a) - rectScore(b));
    return headerButtons[0] || null;
  };
  const findFallbackButton = () => {
    const nodes = Array.from(
      document.querySelectorAll('button,[role="button"],a,div,span')
    ).filter(visible).map((el) => {
      const rect = el.getBoundingClientRect();
      const inHeader = Boolean(el.closest('#douyin-header,#douyin-header-menuCt'));
      const topRight = rect.top < Math.max(160, window.innerHeight * 0.25) &&
        rect.left > window.innerWidth * 0.45;
      const primary = /semi-button-primary|primary|red|login/i.test(el.className || '');
      return {
        el,
        text: text(el),
        rect,
        area: rect.width * rect.height,
        inHeader,
        topRight,
        primary
      };
    }).filter((item) => {
      return item.text === LOGIN_TEXT && (item.inHeader || item.topRight || item.primary);
    });
    nodes.sort((a, b) => {
      const score = (item) => {
        let value = item.area || 100000;
        if (item.el.tagName === 'BUTTON') {
          value -= 5000;
        }
        if (item.inHeader) {
          value -= 3000;
        }
        if (item.primary) {
          value -= 2000;
        }
        if (item.topRight) {
          value -= 1500;
        }
        return value;
      };
      return score(a) - score(b);
    });
    return nodes[0] ? nodes[0].el : null;
  };

  let lastButtonText = '';
  let lastMethod = '';
  for (let attempt = 1; attempt <= 6; attempt += 1) {
    const button = findHeaderButton() || findFallbackButton();
    if (!button) {
      return {
        success: false,
        error: 'Top-right Douyin login button not found',
        marker_found: false,
        attempts: attempt - 1
      };
    }

    const clicked = clickElement(button);
    lastButtonText = text(clicked);
    lastMethod = button.closest('#douyin-header,#douyin-header-menuCt,#douyin-right-container') ||
      /semi-button-primary/i.test(button.className || '') ?
        'top_right_login_button' :
        'fallback_login_button';
    await pause(650);
    if (markerVisible()) {
      return {
        success: true,
        clicked: true,
        method: lastMethod,
        text: lastButtonText,
        marker_found: true,
        attempts: attempt
      };
    }
  }

  return {
    success: false,
    error: 'Douyin login popup marker not found after clicking login',
    clicked: true,
    method: lastMethod,
    text: lastButtonText,
    marker_found: false,
    attempts: 6
  };
})()
""",
    )


def _ensure_login_popup_visible(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const POPUP_MARKER = '\\u767b\\u5f55\\u540e\\u514d\\u8d39\\u7545\\u4eab\\u9ad8\\u6e05\\u89c6\\u9891';
  const PANEL_SELECTOR = [
    '#login-panel-new',
    '#douyin-login-new-id',
    '[id*="login-panel" i]',
    '[class*="login-panel" i]',
    '[id*="douyin-login" i]',
    '[class*="douyin-login" i]'
  ].join(',');
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const marker = Array.from(document.querySelectorAll('body,' + PANEL_SELECTOR)).find((el) => {
    return visible(el) && compactText(el).includes(POPUP_MARKER);
  });
  if (!marker) {
    return {
      success: false,
      marker_found: false,
      error: 'Douyin login popup marker not found'
    };
  }
  return {
    success: true,
    marker_found: true,
    marker_text: POPUP_MARKER
  };
})()
""",
    )


def _ensure_sms_login_mode(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const PANEL_SELECTOR = [
    '#login-panel-new',
    '#douyin-login-new-id',
    '[id*="login-panel" i]',
    '[class*="login-panel" i]',
    '[id*="douyin-login" i]',
    '[class*="douyin-login" i]'
  ].join(',');
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const textOf = (el) => [
    el.placeholder || '',
    el.type || '',
    el.name || '',
    el.id || '',
    el.autocomplete || '',
    el.inputMode || '',
    el.getAttribute('aria-label') || ''
  ].join(' ').toLowerCase();
  const hasPhoneInput = Array.from(document.querySelectorAll('input')).some((el) => {
    return visible(el) &&
      (Boolean(el.closest(PANEL_SELECTOR)) || el.id === 'normal-input' || el.name === 'normal-input') &&
      /(请输入手机号|手机号|手机|phone|mobile|tel|normal-input)/i.test(textOf(el));
  });
  if (hasPhoneInput) {
    return {success: true, already_sms_mode: true};
  }

  const panel = Array.from(document.querySelectorAll(PANEL_SELECTOR)).find(visible) ||
    document.body;
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const nodes = Array.from(
    panel.querySelectorAll('button,[role="button"],a,div,span')
  ).filter(visible).map((el) => {
    const rect = el.getBoundingClientRect();
    const text = compactText(el);
    return {
      el,
      text,
      area: rect.width * rect.height,
      clickable: Boolean(el.closest('button,[role="button"],a')) || el.tagName === 'BUTTON'
    };
  }).filter((item) => {
    if (!item.text || item.text === '登录') {
      return false;
    }
    return item.text.includes('验证码登录') ||
      item.text.includes('短信登录') ||
      item.text.includes('手机登录') ||
      item.text.includes('手机号登录') ||
      item.text.includes('手机号验证码登录') ||
      item.text.includes('验证码登录/注册');
  });

  if (!nodes.length) {
    return {success: false, error: 'SMS login mode switch not found'};
  }

  nodes.sort((a, b) => {
    const score = (item) => {
      let value = item.area || 100000;
      if (item.clickable) {
        value -= 500;
      }
      if (item.text === '验证码登录' || item.text === '短信登录') {
        value -= 300;
      }
      return value;
    };
    return score(a) - score(b);
  });

  const target = nodes[0].el.closest('button,[role="button"],a') || nodes[0].el;
  target.scrollIntoView({block: 'center', inline: 'center'});
  target.click();
  return {
    success: true,
    clicked: true,
    method: 'sms_login_mode_switch',
    text: compactText(target) || nodes[0].text
  };
})()
""",
    )


def _fill_phone(run_js_fn, phone_number):
    return _run_js_dict(
        run_js_fn,
        """
(async () => {
  const phone = PHONE_NUMBER;
  const PANEL_SELECTOR = [
    '#login-panel-new',
    '#douyin-login-new-id',
    '[id*="login-panel" i]',
    '[class*="login-panel" i]',
    '[id*="douyin-login" i]',
    '[class*="douyin-login" i]'
  ].join(',');
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const textOf = (el) => [
    el.placeholder || '',
    el.type || '',
    el.name || '',
    el.id || '',
    el.autocomplete || '',
    el.inputMode || '',
    el.getAttribute('aria-label') || ''
  ].join(' ').toLowerCase();
  const inLoginPanel = (el) => {
    return Boolean(el.closest(PANEL_SELECTOR)) ||
      el.id === 'normal-input' || el.name === 'normal-input';
  };
  const denied = (text) => {
    return /(验证码|code|密码|password|国家|地区|area|country|邮箱|email|搜索|search)/i.test(text);
  };
  const phoneHint = (text) => {
    return /(请输入手机号|手机号|手机|phone|mobile|tel|normal-input)/i.test(text);
  };
  const inputs = Array.from(document.querySelectorAll('input')).filter(visible);
  let target = inputs.find((el) => {
    const text = textOf(el);
    return inLoginPanel(el) && phoneHint(text) && !denied(text);
  });
  if (!target) {
    target = inputs.find((el) => {
      const text = textOf(el);
      const type = (el.type || '').toLowerCase();
      return inLoginPanel(el) && !denied(text) &&
        (type === 'tel' || el.id === 'normal-input' || el.name === 'normal-input');
    });
  }
  if (!target) {
    return {success: false, error: 'Phone input not found in Douyin login panel'};
  }

  const pause = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const descriptor = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
  const setValue = (value) => {
    if (descriptor && descriptor.set) {
      descriptor.set.call(target, value);
    } else {
      target.value = value;
    }
  };
  const emitInput = (inputType, data) => {
    try {
      target.dispatchEvent(new InputEvent('input', {
        bubbles: true,
        cancelable: true,
        inputType,
        data
      }));
    } catch (error) {
      target.dispatchEvent(new Event('input', {bubbles: true}));
    }
  };
  const emitKeyboard = (type, key) => {
    try {
      target.dispatchEvent(new KeyboardEvent(type, {
        bubbles: true,
        cancelable: true,
        key,
        code: /^\\d$/.test(key) ? `Digit${key}` : '',
        charCode: key.length === 1 ? key.charCodeAt(0) : 0,
        keyCode: key.length === 1 ? key.charCodeAt(0) : 0,
        which: key.length === 1 ? key.charCodeAt(0) : 0
      }));
    } catch (error) {}
  };

  target.scrollIntoView({block: 'center', inline: 'center'});
  target.focus();
  target.click();
  setValue('');
  emitInput('deleteContentBackward', null);
  await pause(30);

  for (const char of phone) {
    emitKeyboard('keydown', char);
    emitKeyboard('keypress', char);
    try {
      target.dispatchEvent(new InputEvent('beforeinput', {
        bubbles: true,
        cancelable: true,
        inputType: 'insertText',
        data: char
      }));
    } catch (error) {}
    setValue((target.value || '') + char);
    emitInput('insertText', char);
    emitKeyboard('keyup', char);
    await pause(25);
  }

  target.dispatchEvent(new Event('change', {bubbles: true}));
  await pause(120);
  const digits = (target.value || '').replace(/\\D/g, '');
  return {
    success: digits === phone,
    error: digits === phone ? '' : 'Phone input did not accept all digits',
    placeholder: target.placeholder || '',
    name: target.name || '',
    id: target.id || '',
    type: target.type || '',
    value: target.value || ''
  };
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
  const PANEL_SELECTOR = [
    '#login-panel-new',
    '#douyin-login-new-id',
    '[id*="login-panel" i]',
    '[class*="login-panel" i]',
    '[id*="douyin-login" i]',
    '[class*="douyin-login" i]'
  ].join(',');
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const textOf = (el) => [
    el.placeholder || '',
    el.type || '',
    el.name || '',
    el.id || '',
    el.autocomplete || '',
    el.inputMode || '',
    el.getAttribute('aria-label') || ''
  ].join(' ').toLowerCase();
  const inLoginPanel = (el) => {
    return Boolean(el.closest(PANEL_SELECTOR)) ||
      el.id === 'button-input' || el.name === 'button-input' ||
      el.id === 'douyin_login_comp_button_input_id';
  };
  const phoneInput = Array.from(document.querySelectorAll('input')).find((el) => {
    return visible(el) && inLoginPanel(el) &&
      /(请输入手机号|手机号|手机|phone|mobile|tel|normal-input)/i.test(textOf(el));
  });
  const codeInput = Array.from(document.querySelectorAll('input')).find((el) => {
    return visible(el) && inLoginPanel(el) &&
      /(请输入验证码|验证码|code|button-input)/i.test(textOf(el));
  });
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const clickLikeHuman = (el) => {
    const target = el.closest('button,[role="button"],a') || el;
    target.scrollIntoView({block: 'center', inline: 'center'});
    const rect = target.getBoundingClientRect();
    const clientX = rect.left + rect.width / 2;
    const clientY = rect.top + rect.height / 2;
    const eventInit = {
      bubbles: true,
      cancelable: true,
      view: window,
      clientX,
      clientY,
      button: 0,
      buttons: 1
    };
    try {
      target.dispatchEvent(new PointerEvent('pointerdown', eventInit));
      target.dispatchEvent(new PointerEvent('pointerup', {...eventInit, buttons: 0}));
    } catch (error) {}
    target.dispatchEvent(new MouseEvent('mousedown', eventInit));
    target.dispatchEvent(new MouseEvent('mouseup', {...eventInit, buttons: 0}));
    target.dispatchEvent(new MouseEvent('click', {...eventInit, buttons: 0}));
    if (typeof target.click === 'function') {
      target.click();
    }
    return target;
  };
  const nodes = Array.from(
    document.querySelectorAll('button,[role="button"],a,div,span,p')
  ).filter(visible).map((el) => {
    const text = compactText(el);
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    const phoneRect = phoneInput ? phoneInput.getBoundingClientRect() : null;
    const belowPhone = phoneRect ? rect.top >= phoneRect.bottom - 12 : false;
    const nearPhoneX = phoneRect ?
      rect.right >= phoneRect.left - 20 && rect.left <= phoneRect.right + 160 :
      false;
    const redText = /rgb\\(\\s*(2[0-9]{2}|1[8-9][0-9])\\s*,\\s*([0-8]?[0-9]|9[0-9])\\s*,\\s*([0-9]{1,2}|1[0-4][0-9])\\s*\\)|#?fe2c55|#?ff/i.test(
      style.color || ''
    );
    return {el, text, rect, style, belowPhone, nearPhoneX, redText};
  }).filter((item) => {
    if (!inLoginPanel(item.el) || /收不到|验证码登录|短信登录|手机登录/.test(item.text)) {
      return false;
    }
    if (item.text === SEND_TEXT || item.text === GET_TEXT) {
      return true;
    }
    if (item.text.includes(SEND_TEXT) && item.text.length <= 24) {
      return true;
    }
    if (item.text.includes(GET_TEXT) && item.text.length <= 24) {
      return true;
    }
    return false;
  });

  if (!nodes.length) {
    return {success: false, error: 'Get-code button not found'};
  }

  nodes.sort((a, b) => {
    const score = (item) => {
      let value = item.el.id === 'douyin_login_comp_button_input_id' ? -50 : 0;
      if (item.text === SEND_TEXT) {
        value -= 120;
      } else if (item.text.includes(SEND_TEXT)) {
        value -= 90;
      } else if (item.text === GET_TEXT) {
        value -= 50;
      }
      if (item.belowPhone && item.nearPhoneX) {
        value -= 100;
      } else if (item.belowPhone) {
        value -= 60;
      }
      if (item.redText) {
        value -= 40;
      }
      value += Math.max(0, item.text.length - 5);
      if (codeInput) {
        const inputRect = codeInput.getBoundingClientRect();
        const rect = item.rect;
        const inputCenterY = inputRect.top + inputRect.height / 2;
        const centerY = rect.top + rect.height / 2;
        const sameRow = rect.bottom >= inputRect.top - 8 && rect.top <= inputRect.bottom + 8;
        const rightOfCodeInput = rect.left >= inputRect.left + inputRect.width * 0.45;
        const horizontalDistance = Math.max(0, rect.left - inputRect.right);
        value += Math.abs(centerY - inputCenterY) / 10;
        if (sameRow) {
          value -= 30;
        }
        if (rightOfCodeInput) {
          value -= 20;
        }
        value += Math.min(horizontalDistance / 20, 20);
      }
      return value;
    };
    return score(a) - score(b);
  });

  const target = nodes[0].el.closest('button,[role="button"],a') || nodes[0].el;
  if (target.disabled || target.getAttribute('aria-disabled') === 'true') {
    return {success: false, error: 'Get-code button is disabled', text: nodes[0].text};
  }

  const clicked = clickLikeHuman(nodes[0].el);
  return {
    success: true,
    text: nodes[0].text,
    id: clicked.id || '',
    method: nodes[0].belowPhone ? 'phone_input_below_red_text' : 'verification_code_button',
    near_code_input: Boolean(codeInput),
    below_phone_input: Boolean(nodes[0].belowPhone),
    red_text: Boolean(nodes[0].redText)
  };
})()
""",
    )


def _retry_browser_step(step_name, action_fn, steps, wait_fn, *, attempts, interval):
    result = {"success": False, "error": "step not attempted"}
    for attempt in range(1, attempts + 1):
        result = action_fn()
        suffix = "" if attempt == 1 else f"_attempt_{attempt}"
        steps.append({"step": f"{step_name}{suffix}", "result": result})
        if result.get("success"):
            return result
        if attempt < attempts and interval:
            steps.append(
                {
                    "step": f"wait_before_{step_name}_attempt_{attempt + 1}",
                    "result": wait_fn(interval),
                }
            )
    return result


def run(
    phone_number,
    login_url=DEFAULT_LOGIN_URL,
    wait_seconds=1,
    *,
    goto_fn=None,
    run_js_fn=None,
    wait_fn=None,
    get_url_fn=None,
    get_text_fn=None,
    log_fn=None,
):
    """Prepare Douyin SMS login and stop before manual code entry."""
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

        nav_result = goto_fn(login_url)
        steps.append({"step": "navigate", "result": nav_result})
        if wait_seconds:
            steps.append({"step": "wait_after_navigation", "result": wait_fn(wait_seconds)})

        blocked = _detect_blocked(get_url_fn, get_text_fn)
        if blocked:
            blocked["steps"] = steps
            log_fn("Douyin login blocked by verification page")
            return blocked

        open_result = _open_login_panel(run_js_fn)
        steps.append({"step": "open_login_panel", "result": open_result})
        if not open_result.get("success"):
            return {
                "success": False,
                "error": "Failed to open Douyin login panel",
                "steps": steps,
            }
        if wait_seconds:
            steps.append({"step": "wait_after_open_login", "result": wait_fn(wait_seconds)})

        popup_result = _ensure_login_popup_visible(run_js_fn)
        steps.append({"step": "confirm_login_popup", "result": popup_result})
        if not popup_result.get("success"):
            return {
                "success": False,
                "error": "Failed to confirm Douyin login popup",
                "steps": steps,
            }

        sms_mode_result = _retry_browser_step(
            "ensure_sms_login_mode",
            lambda: _ensure_sms_login_mode(run_js_fn),
            steps,
            wait_fn,
            attempts=3,
            interval=0.5,
        )
        if sms_mode_result.get("clicked") and wait_seconds:
            steps.append(
                {"step": "wait_after_sms_login_mode", "result": wait_fn(wait_seconds)}
            )

        fill_result = _retry_browser_step(
            "fill_phone",
            lambda: _fill_phone(run_js_fn, phone),
            steps,
            wait_fn,
            attempts=6,
            interval=0.5,
        )
        if not fill_result.get("success"):
            return {
                "success": False,
                "error": "Failed to fill Douyin phone number",
                "steps": steps,
            }

        get_code_result = _retry_browser_step(
            "click_get_code",
            lambda: _click_get_code(run_js_fn),
            steps,
            wait_fn,
            attempts=6,
            interval=0.5,
        )
        if not get_code_result.get("success"):
            return {
                "success": False,
                "error": "Failed to request Douyin verification code",
                "steps": steps,
            }

        if wait_seconds:
            steps.append({"step": "wait_after_get_code", "result": wait_fn(wait_seconds)})

        blocked = _detect_blocked(get_url_fn, get_text_fn)
        if blocked:
            blocked["steps"] = steps
            log_fn("Douyin requires extra verification after requesting code")
            return blocked

        log_fn("Douyin verification code requested; manual code entry required")
        return {
            "success": True,
            "requires_manual_code": True,
            "phone_number": phone,
            "steps": steps,
            "message": "Please enter the SMS verification code manually in the browser.",
        }

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        log_fn(f"Douyin login preparation failed: {error}")
        return {"success": False, "error": error, "steps": steps}
