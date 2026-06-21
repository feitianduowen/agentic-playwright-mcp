"""微博搜索适配器。"""


def run(keyword: str):
    """在微博搜索。

    Args:
        keyword: 搜索关键词。
    """
    goto("https://s.weibo.com")
    wait_for_navigation()
    fill("#search-input", keyword)
    click("[node-type='searchbtn']")
    wait_for_navigation()
    log(f"微博搜索完成: {keyword}")


# 选择器备选方案:
# search_input: #search-input → input[name='q'] → .search-input
# search_button: [node-type='searchbtn'] → .search-btn
