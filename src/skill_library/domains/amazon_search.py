"""Amazon 搜索适配器。"""


def run(keyword: str):
    """在 Amazon 搜索商品。

    Args:
        keyword: 搜索关键词。
    """
    goto("https://www.amazon.com")
    wait_for_navigation()
    fill("#twotabsearchtextbox", keyword)
    click("#nav-search-submit-button")
    wait_for_navigation()
    log(f"Amazon 搜索完成: {keyword}")


# 选择器备选方案:
# search_input: #twotabsearchtextbox → input[name='field-keywords']
# search_button: #nav-search-submit-button → .nav-search-submit
