"""YouTube 搜索适配器。"""


def run(keyword: str):
    """在 YouTube 搜索视频。

    Args:
        keyword: 搜索关键词。
    """
    goto("https://www.youtube.com")
    wait_for_navigation()
    fill("input[name='search_query']", keyword)
    click("button#search-icon-legacy")
    wait_for_navigation()
    log(f"YouTube 搜索完成: {keyword}")


# 选择器备选方案:
# search_input: input[name='search_query'] → #search → input[id='search']
# search_button: button#search-icon-legacy → button[aria-label='搜索']
