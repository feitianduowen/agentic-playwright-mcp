# Bilibili 文章投稿

用于完成 Bilibili 短信登录后进入文章投稿页，填写标题和正文，并点击右下角蓝色“发布”按钮。

真人认证和短信验证码输入必须由用户在浏览器弹窗中手动完成。

```python
from skill_library.send.bilibili_publish import run

run("13574133406", "文章标题", "文章正文")
```
