# Bilibili 视频评论

用于完成 Bilibili 短信登录后进入视频页面，填写评论内容并点击发送。

真人认证和短信验证码输入必须由用户在浏览器弹窗中手动完成。

```python
from skill_library.comment.bilibili_comment import run

# 在指定视频下发布评论
run("13574133406", "这是一条测试评论", "https://www.bilibili.com/video/BV1oh7b6xE4R")

# 使用默认视频URL
run("13574133406", "test")
```
