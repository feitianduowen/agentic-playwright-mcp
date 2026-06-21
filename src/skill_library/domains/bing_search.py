"""Bing 搜索适配器。"""


def run(keyword: str):
    """在 Bing 搜索关键词。

    Args:
        keyword: 搜索关键词。
    """
    goto("https://www.bing.com")
    wait_for_navigation()
    fill("#sb_form_q", keyword)
    click("#sb_form_go")
    wait_for_navigation()
    log(f"Bing 搜索完成: {keyword}")


# 选择器备选方案:
# search_input: #sb_form_q → textarea[name='q']
# search_button: #sb_form_go → button[type='submit']
