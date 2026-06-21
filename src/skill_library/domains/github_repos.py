"""GitHub 仓库列表适配器。"""


def run(username: str = ""):
    """查看 GitHub 仓库列表。

    Args:
        username: GitHub 用户名（为空时查看自己的仓库）。
    """
    if username:
        goto(f"https://github.com/{username}?tab=repositories")
    else:
        goto("https://github.com")
    wait_for_navigation()
    text = get_text()
    log(f"GitHub 仓库页面加载完成")
    print(text[:2000])


# 选择器备选方案:
# repo_list: .repo-list → [data-filterable-for='your-repos-filter']
# repo_item: .repo-list-item → .Box-row
