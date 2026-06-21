"""Outlook 收件箱适配器。"""


def run():
    """打开 Outlook 收件箱。"""
    goto("https://outlook.live.com/mail/")
    wait_for_navigation()
    text = get_text()
    log("Outlook 收件箱加载完成")
    print(text[:2000])


# 选择器备选方案:
# inbox_link: a[title='收件箱'] → [data-testid='folder-tree-inbox']
# compose_button: button[aria-label='新建邮件'] → [role='button'][name='新建邮件']
