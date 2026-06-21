"""知乎搜索适配器。"""


def run(keyword: str):
    """在知乎搜索。

    Args:
        keyword: 搜索关键词。
    """
    goto("https://www.zhihu.com/search")
    wait_for_navigation()
    fill(".Input-wrapper input", keyword)
    click(".SearchBar-searchButton")
    wait_for_navigation()
    log(f"知乎搜索完成: {keyword}")


# 选择器备选方案:
# search_input: .Input-wrapper input → input[name='q'] → #Popover1-toggle
# search_button: .SearchBar-searchButton → button[type='submit']
