"""GitHub 搜索适配器。"""


def run(keyword: str, search_type: str = "repositories"):
    """在 GitHub 搜索仓库/代码/用户。

    Args:
        keyword: 搜索关键词。
        search_type: 搜索类型 (repositories/code/users/issues)。
    """
    goto("https://github.com/search")
    wait_for_navigation()
    fill("input[name='q']", keyword)
    click("button[type='submit']")
    wait_for_navigation()
    log(f"GitHub 搜索完成: {keyword} (类型: {search_type})")


# 选择器备选方案:
# search_input: input[name='q'] → #search-input → input[placeholder*='Search']
# search_button: button[type='submit'] → .header-search-button
