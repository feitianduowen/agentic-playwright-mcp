"""Google 搜索适配器。"""


def run(keyword: str):
    """在 Google 搜索关键词。

    Args:
        keyword: 搜索关键词。
    """
    goto("https://www.google.com")
    wait_for_navigation()
    fill("textarea[name='q']", keyword)
    click("input[name='btnK']")
    wait_for_navigation()
    log(f"Google 搜索完成: {keyword}")


# 选择器备选方案:
# search_input: textarea[name='q'] → input[name='q'] → #search
# search_button: input[name='btnK'] → button[type='submit']
