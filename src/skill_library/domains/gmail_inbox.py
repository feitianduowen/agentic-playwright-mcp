"""Gmail 收件箱适配器。"""


def run():
    """打开 Gmail 收件箱。"""
    goto("https://mail.google.com")
    wait_for_navigation()
    text = get_text()
    log("Gmail 收件箱加载完成")
    print(text[:2000])


# 选择器备选方案:
# inbox_link: a[title='收件箱'] → a[href*='#inbox']
# compose_button: .T-I.J-J5-Ji.T-I-KE.L3 → div[role='button'][gh='cm']
