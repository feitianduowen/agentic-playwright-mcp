"""Bilibili search adapter."""


DEFAULT_SEARCH_URL = "https://www.bilibili.com"
SEARCH_RESULT_URL = "https://search.bilibili.com/all?keyword="


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


def _quote(value):
    try:
        return url_quote(value)
    except NameError:
        from urllib.parse import quote_plus

        return quote_plus(value)


def _fill_and_submit(run_js_fn, keyword):
    return _run_js_dict(
        run_js_fn,
        """
(() => {
  const keyword = KEYWORD;
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
    el.getAttribute('aria-label') || '',
    el.getAttribute('title') || ''
  ].join(' ').toLowerCase();
  const deniedInput = (text) => {
    return /(password|login|phone|mobile|tel|验证码|密码|手机号|账号)/i.test(text);
  };
  const candidates = Array.from(document.querySelectorAll([
    '.nav-search-input',
    '.center-search__bar input',
    'input[name="keyword"]',
    'input[placeholder*="搜索"]',
    'input[type="search"]',
    'input[type="text"]'
  ].join(','))).filter(visible).map((el) => {
    const rect = el.getBoundingClientRect();
    const text = textOf(el);
    const inHeader = Boolean(el.closest('.bili-header,.international-header,.bili-header__bar,.center-search-container,.nav-search-content'));
    return {el, rect, text, inHeader};
  }).filter((item) => {
    if (deniedInput(item.text)) {
      return false;
    }
    return item.inHeader ||
      /搜索|search|keyword/.test(item.text) ||
      /nav-search-input|center-search/.test(String(item.el.className || ''));
  });

  if (!candidates.length) {
    return {success: false, error: 'Bilibili search input not found'};
  }

  candidates.sort((a, b) => {
    const score = (item) => {
      let value = 0;
      if (/nav-search-input/.test(String(item.el.className || ''))) {
        value -= 1000;
      }
      if (item.inHeader) {
        value -= 500;
      }
      if (/搜索|search|keyword/.test(item.text)) {
        value -= 200;
      }
      value += item.rect.top;
      value += Math.abs(item.rect.left - window.innerWidth / 2) / 10;
      return value;
    };
    return score(a) - score(b);
  });

  const input = candidates[0].el;
  input.scrollIntoView({block: 'center', inline: 'center'});
  input.focus();
  input.click();

  const descriptor = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
  if (descriptor && descriptor.set) {
    descriptor.set.call(input, keyword);
  } else {
    input.value = keyword;
  }
  try {
    input.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      cancelable: true,
      inputType: 'insertText',
      data: keyword
    }));
  } catch (error) {
    input.dispatchEvent(new Event('input', {bubbles: true}));
  }
  input.dispatchEvent(new Event('change', {bubbles: true}));

  const inputRect = input.getBoundingClientRect();
  const buttonCandidates = Array.from(document.querySelectorAll([
    '.nav-search-btn',
    '.center-search__bar button',
    '.search-btn',
    'button[type="submit"]',
    '[role="button"]',
    'button',
    'a'
  ].join(','))).filter(visible).map((el) => {
    const rect = el.getBoundingClientRect();
    const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || el.getAttribute('title') || '')
      .trim().replace(/\\s+/g, '');
    const className = String(el.className || '');
    const sameRow = rect.bottom >= inputRect.top - 12 && rect.top <= inputRect.bottom + 12;
    const nearInput = rect.left >= inputRect.left - 24 && rect.left <= inputRect.right + 120;
    const inSearch = Boolean(el.closest('.nav-search-content,.center-search-container,.center-search__bar,form'));
    return {el, rect, text, className, sameRow, nearInput, inSearch};
  }).filter((item) => {
    if (item.el === input) {
      return false;
    }
    if (/login|avatar|投稿|登录/.test(item.text + item.className)) {
      return false;
    }
    return /nav-search-btn|search-btn|submit/.test(item.className) ||
      item.text === '搜索' ||
      (item.sameRow && item.nearInput && item.inSearch);
  });

  if (!buttonCandidates.length) {
    const keyboardInit = {
      bubbles: true,
      cancelable: true,
      key: 'Enter',
      code: 'Enter',
      keyCode: 13,
      which: 13
    };
    input.dispatchEvent(new KeyboardEvent('keydown', keyboardInit));
    input.dispatchEvent(new KeyboardEvent('keypress', keyboardInit));
    input.dispatchEvent(new KeyboardEvent('keyup', keyboardInit));
    const form = input.closest('form');
    if (form) {
      try {
        if (typeof form.requestSubmit === 'function') {
          form.requestSubmit();
        } else {
          form.submit();
        }
      } catch (error) {}
    }
    return {
      success: true,
      filled: true,
      clicked: false,
      method: 'enter_key_fallback',
      value: input.value || ''
    };
  }

  buttonCandidates.sort((a, b) => {
    const score = (item) => {
      let value = 0;
      if (/nav-search-btn/.test(item.className)) {
        value -= 1000;
      }
      if (/search-btn/.test(item.className)) {
        value -= 700;
      }
      if (item.text === '搜索') {
        value -= 300;
      }
      if (item.sameRow && item.nearInput) {
        value -= 200;
      }
      value += Math.abs((item.rect.top + item.rect.height / 2) - (inputRect.top + inputRect.height / 2));
      value += Math.max(0, item.rect.left - inputRect.right) / 10;
      return value;
    };
    return score(a) - score(b);
  });

  const button = buttonCandidates[0].el.closest('button,[role="button"],a') || buttonCandidates[0].el;
  button.scrollIntoView({block: 'center', inline: 'center'});
  button.click();

  return {
    success: true,
    filled: true,
    clicked: true,
    value: input.value || '',
    input_selector: input.className || input.name || input.placeholder || '',
    button_selector: button.className || button.getAttribute('aria-label') || button.textContent || ''
  };
})()
""".replace("KEYWORD", _js_string(keyword)),
    )


def run(
    keyword: str,
    *,
    goto_fn=None,
    run_js_fn=None,
    wait_fn=None,
    wait_for_navigation_fn=None,
    get_url_fn=None,
    log_fn=None,
):
    """Search Bilibili by filling the header input and submitting it."""
    if goto_fn is None:
        goto_fn = goto
    if run_js_fn is None:
        run_js_fn = run_js
    if wait_fn is None:
        wait_fn = wait
    if wait_for_navigation_fn is None:
        wait_for_navigation_fn = wait_for_navigation
    if get_url_fn is None:
        get_url_fn = get_url

    log_fn = _resolve_log(log_fn)
    text = str(keyword).strip()
    if not text:
        raise ValueError("Bilibili search requires a keyword")

    steps = []
    nav_result = goto_fn(DEFAULT_SEARCH_URL)
    steps.append({"step": "navigate", "result": nav_result})
    steps.append({"step": "wait_after_navigation", "result": _safe_call(wait_fn, "", 1)})

    submit_result = _fill_and_submit(run_js_fn, text)
    steps.append({"step": "fill_and_submit_search", "result": submit_result})
    if not submit_result.get("success"):
        return {
            "success": False,
            "error": "Failed to fill and submit Bilibili search input",
            "steps": steps,
        }

    steps.append(
        {
            "step": "wait_for_search_navigation",
            "result": _safe_call(wait_for_navigation_fn, "", 10),
        }
    )

    current_url = str(_safe_call(get_url_fn, "") or "")
    quoted = _quote(text)
    if "search.bilibili.com" not in current_url or "keyword=" not in current_url:
        fallback_url = f"{SEARCH_RESULT_URL}{quoted}"
        steps.append({"step": "fallback_search_navigation", "result": goto_fn(fallback_url)})
        current_url = str(_safe_call(get_url_fn, fallback_url) or fallback_url)

    log_fn(f"Bilibili 搜索完成: {text}")
    return {
        "success": True,
        "keyword": text,
        "url": current_url,
        "steps": steps,
    }


# Selector fallback notes for interactive search mode:
# search_input: .nav-search-input -> .center-search__bar input -> input[name='keyword']
# search_button: .nav-search-btn -> .center-search__bar button -> .search-btn
