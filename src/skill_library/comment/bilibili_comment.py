"""Bilibili video comment publishing adapter."""

try:
    from src.layer_2 import controls as _controls
except Exception:
    _controls = None


DEFAULT_LOGIN_URL = "https://www.bilibili.com"
DEFAULT_VIDEO_URL = "https://www.bilibili.com/video/BV1oh7b6xE4R"


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
        raise ValueError("Bilibili comment requires a valid 11-digit phone number")

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
  const loggedIn = (avatar && !loginPopup) || (!loginEntry && !loginPopup);
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


def _reload_page(run_js_fn):
    """Reload the current page."""
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  location.reload();
  return {success: true};
})()
""",
    )


def _prepare_sms_login_on_video(phone, goto_fn, run_js_fn, wait_fn, get_url_fn, get_text_fn, steps):
    """Prepare SMS login on the video page."""
    state = _detect_login_state(run_js_fn)
    steps.append({"step": "detect_login_state", "result": state})
    if state.get("logged_in"):
        return {"success": True, "already_logged_in": True}

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


def _wait_for_login_completion_on_video(run_js_fn, wait_fn, steps, max_wait_seconds, interval_seconds):
    """Wait for login to complete on video page, with extra wait for human verification."""
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


def _find_comment_input(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
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

  const commentKeywords = [
    '\\u8bc4\\u8bba', '\\u8bc4\\u8bb0', '\\u53d1\\u8868\\u4f60\\u7684\\u770b\\u6cd5',
    '\\u5594\\u54e6\\u8bc4\\u8bb0\\u4e00\\u4e0b', '\\u6280\\u672f\\u8bc4\\u8bba',
    '\\u70b9\\u51fb\\u8bc4\\u8bba', 'comment', 'reply', '\\u56de\\u590d'
  ];

  const inputCandidates = Array.from(document.querySelectorAll(
    'textarea,[contenteditable="true"],[role="textbox"],[data-placeholder]'
  )).filter(visible).filter((el) => {
    const label = labelOf(el);
    const nearText = compactText(el.parentElement || el.parentElement?.parentElement || el);
    return commentKeywords.some((kw) => label.includes(kw) || nearText.includes(kw)) ||
      /textarea.*comment|comment.*textarea/i.test(String(el.className || el.id || ''));
  });

  if (inputCandidates.length) {
    return {success: true, found: true, selector: inputCandidates[0].className || inputCandidates[0].id || inputCandidates[0].tagName};
  }

  const textInputCandidates = Array.from(document.querySelectorAll('textarea,input')).filter(visible).filter((el) => {
    const label = labelOf(el);
    return /(评论|comment|回复|reply)/i.test(label) && el.tagName !== 'INPUT';
  });

  if (textInputCandidates.length) {
    return {success: true, found: true, selector: textInputCandidates[0].className || textInputCandidates[0].id || textInputCandidates[0].tagName};
  }

  const placeholderHints = ['说点什么', '评论', '留下你的精彩评论', '文明上网', '发表评论'];
  const fallbackCandidates = Array.from(document.querySelectorAll('textarea,[contenteditable="true"],[role="textbox"]'))
    .filter(visible).filter((el) => {
      const ph = el.placeholder || el.getAttribute('data-placeholder') || '';
      return placeholderHints.some((hint) => ph.includes(hint));
    });

  if (fallbackCandidates.length) {
    return {success: true, found: true, selector: 'fallback', method: 'placeholder_hint'};
  }

  return {success: false, error: 'Bilibili comment input not found'};
})()
""",
    )


def _fill_comment(run_js_fn, comment_text):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const comment = COMMENT_TEXT;
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

  const commentKeywords = [
    '\\u8bc4\\u8bba', '\\u8bc4\\u8bb0', '\\u53d1\\u8868\\u4f60\\u7684\\u770b\\u6cd5',
    '\\u5594\\u54e6\\u8bc4\\u8bb0\\u4e00\\u4e0b', '\\u6280\\u672f\\u8bc4\\u8bba',
    '\\u70b9\\u51fb\\u8bc4\\u8bba', 'comment', 'reply'
  ];

  let target = null;
  const allInputs = Array.from(document.querySelectorAll(
    'textarea,[contenteditable="true"],[role="textbox"],[data-placeholder]'
  )).filter(visible);

  for (const el of allInputs) {
    const label = labelOf(el);
    const nearText = compactText(el.parentElement || el.parentElement?.parentElement || el);
    if (commentKeywords.some((kw) => label.includes(kw) || nearText.includes(kw))) {
      target = el;
      break;
    }
  }

  if (!target) {
    const placeholderHints = ['说点什么', '评论', '留下你的精彩评论', '文明上网', '发表评论'];
    for (const el of allInputs) {
      const ph = el.placeholder || el.getAttribute('data-placeholder') || '';
      if (placeholderHints.some((hint) => ph.includes(hint))) {
        target = el;
        break;
      }
    }
  }

  if (!target) {
    const textInputs = Array.from(document.querySelectorAll('textarea')).filter(visible);
    for (const el of textInputs) {
      const label = labelOf(el);
      if (/(评论|comment|回复|reply)/i.test(label)) {
        target = el;
        break;
      }
    }
  }

  if (!target) {
    return {success: false, error: 'Comment input not found'};
  }

  target.scrollIntoView({block: 'center', inline: 'center'});
  target.focus();

  if (target.tagName === 'TEXTAREA' || target.tagName === 'INPUT') {
    const descriptor = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value') ||
                       Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
    if (descriptor && descriptor.set) {
      descriptor.set.call(target, comment);
    } else {
      target.value = comment;
    }
    target.dispatchEvent(new Event('input', {bubbles: true}));
    target.dispatchEvent(new Event('change', {bubbles: true}));
  } else {
    target.innerHTML = '';
    target.dispatchEvent(new Event('focus', {bubbles: true}));
    try {
      target.dispatchEvent(new InputEvent('beforeinput', {bubbles: true, cancelable: true, inputType: 'insertText', data: comment}));
    } catch (e) {}
    target.innerText = comment;
    try {
      target.dispatchEvent(new InputEvent('input', {bubbles: true}));
    } catch (e) {
      target.dispatchEvent(new Event('input', {bubbles: true}));
    }
  }

  target.dispatchEvent(new Event('blur', {bubbles: true}));
  const value = target.value || target.innerText || target.textContent || '';
  return {success: value.includes(comment.split('\\n')[0]), value: value.substring(0, 100)};
})()
""".replace("COMMENT_TEXT", _js_string(comment_text)),
    )


def _click_send_comment(run_js_fn):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const SEND_TEXT = '\\u53d1\\u5e03';
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    return style && style.visibility !== 'hidden' && style.display !== 'none' &&
      (el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  };
  const compactText = (el) => (el.innerText || el.textContent || '').trim().replace(/\\s+/g, '');
  const labelOf = (el) => [
    el.placeholder || '',
    el.getAttribute('aria-label') || '',
    el.getAttribute('title') || '',
    el.name || '',
    el.id || '',
    String(el.className || '')
  ].join(' ').toLowerCase();

  const sendKeywords = [
    '\\u53d1\\u5e03', '\\u53d1\\u9001', '\\u63d0\\u4ea4', '\\u63d0\\u4ea4\\u8bc4\\u8bba',
    '\\u8bc4\\u8bba', '\\u56de\\u590d', 'submit', 'send', 'post'
  ];

  let candidates = Array.from(document.querySelectorAll(
    'button,[role="button"],a,div,span'
  )).filter(visible).map((el) => {
    const rect = el.getBoundingClientRect();
    const text = compactText(el);
    const label = labelOf(el);
    return {el, text, label, rect, clickable: Boolean(el.closest('button,[role="button"],a')) || el.tagName === 'BUTTON'};
  }).filter((item) => {
    if (!item.text) return false;
    if (/取消|关闭|删除|编辑/.test(item.text)) return false;
    return sendKeywords.some((kw) => item.text.includes(kw) || item.label.includes(kw));
  });

  if (candidates.length) {
    candidates.sort((a, b) => {
      const score = (item) => {
        let value = 0;
        if (item.text === SEND_TEXT) value -= 500;
        if (item.clickable) value -= 100;
        if (/\\u53d1\\u5e03/.test(item.text)) value -= 200;
        return value;
      };
      return score(a) - score(b);
    });
    const target = candidates[0].el.closest('button,[role="button"],a') || candidates[0].el;
    if (target.disabled || target.getAttribute('aria-disabled') === 'true') {
      return {success: false, error: 'Send button is disabled', text: candidates[0].text};
    }
    target.scrollIntoView({block: 'center', inline: 'center'});
    target.click();
    return {success: true, text: candidates[0].text, method: 'keyword_match'};
  }

  const bottomRightButtons = Array.from(document.querySelectorAll('button,[role="button"]'))
    .filter(visible).filter((el) => {
      const rect = el.getBoundingClientRect();
      const inBottomArea = rect.top > window.innerHeight * 0.5;
      const inRightArea = rect.left > window.innerWidth * 0.4;
      return inBottomArea || inRightArea;
    }).map((el) => {
      const rect = el.getBoundingClientRect();
      const text = compactText(el);
      return {el, text, rect};
    }).filter((item) => item.text && item.text.length <= 10);

  if (bottomRightButtons.length) {
    bottomRightButtons.sort((a, b) => (b.rect.width * b.rect.height) - (a.rect.width * a.rect.height));
    const target = bottomRightButtons[0].el;
    target.scrollIntoView({block: 'center', inline: 'center'});
    target.click();
    return {success: true, text: bottomRightButtons[0].text, method: 'bottom_right_fallback'};
  }

  return {success: false, error: 'Bilibili send comment button not found'};
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
    comment_text,
    video_url=None,
    *,
    max_wait_seconds=300,
    goto_fn=None,
    run_js_fn=None,
    wait_fn=None,
    get_url_fn=None,
    get_text_fn=None,
    log_fn=None,
):
    """Log in to Bilibili on video page, reload, then post comment.

    Flow:
    1. Open video page
    2. Click login button (top right)
    3. Switch to SMS login
    4. Fill phone and send code
    5. Wait for user to complete verification
    6. Wait 30 seconds
    7. Reload page
    8. Find comment input and send
    """
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
        video = str(video_url).strip() if video_url else DEFAULT_VIDEO_URL
        comment = str(comment_text).strip()
        if not comment:
            raise ValueError("Bilibili comment requires comment text")

        # Step 1: Open video page
        log_fn(f"Opening video page: {video}")
        steps.append({"step": "navigate_video", "result": goto_fn(video)})
        steps.append({"step": "wait_after_video_navigation", "result": _safe_call(wait_fn, "", 2)})

        # Step 2-5: Login on video page
        login_result = _prepare_sms_login_on_video(
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
            wait_result = _wait_for_login_completion_on_video(
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
                    "error": "Please complete Bilibili human verification/login before commenting",
                    "steps": steps,
                }

        # Step 6: Wait 30 seconds after login
        log_fn("Login completed. Waiting 30 seconds before reloading...")
        steps.append({"step": "wait_before_reload", "result": _safe_call(wait_fn, "", 30)})

        # Step 7: Reload page
        log_fn("Reloading page...")
        steps.append({"step": "reload_page", "result": _reload_page(run_js_fn)})
        steps.append({"step": "wait_after_reload", "result": _safe_call(wait_fn, "", 3)})

        # Step 8: Find comment input
        input_result = _retry(
            "find_comment_input",
            lambda: _find_comment_input(run_js_fn),
            steps,
            wait_fn,
            attempts=5,
            interval=1,
        )
        if not input_result.get("success"):
            return {
                "success": False,
                "error": "Failed to find Bilibili comment input",
                "steps": steps,
            }

        # Fill comment
        fill_result = _retry(
            "fill_comment",
            lambda: _fill_comment(run_js_fn, comment),
            steps,
            wait_fn,
            attempts=5,
            interval=1,
        )
        if not fill_result.get("success"):
            return {
                "success": False,
                "error": "Failed to fill Bilibili comment",
                "steps": steps,
            }

        # Click send
        send_result = _retry(
            "click_send_comment",
            lambda: _click_send_comment(run_js_fn),
            steps,
            wait_fn,
            attempts=5,
            interval=1,
        )
        if not send_result.get("success"):
            return {
                "success": False,
                "error": "Failed to click Bilibili send comment button",
                "steps": steps,
            }

        log_fn("Bilibili comment published successfully")
        return {
            "success": True,
            "comment": comment,
            "video_url": video,
            "url": _safe_call(get_url_fn, ""),
            "steps": steps,
            "message": "Bilibili comment filled and send button clicked.",
        }

    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        log_fn(f"Bilibili comment failed: {error}")
        return {"success": False, "error": error, "steps": steps}
