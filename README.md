# Agentic Playwright MCP

让 AI Agent 写 Python 脚本来控制浏览器的 MCP Server 框架。

基于 Playwright，支持可选的 [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) 反检测引擎。

## 核心理念

**AI 不是逐个调用工具，而是编写 Python 脚本。**

```
用户意图 → AI 查找技能 → AI 参考范例生成脚本 → 脚本引擎执行 → 浏览器操作
   ↳ 若未命中 → 检索通用模板 → 生成临时脚本 → 沙箱执行
   ↳ 若失败 → 自愈机制尝试 → 视觉 fallback → 记录新经验
```

## 当前能力

| 场景 | 程度 | 说明 |
|------|------|------|
| **简单任务**（搜索、导航、截图） | ✅ 可用 | 直接跑通 |
| **中等任务**（登录、填表、翻页） | ⚠️ 有限 | 有模板，需要适配站点 |
| **复杂任务**（多步骤、跨页面） | ⚠️ 有限 | Agent 循环能跑，推理能力有限 |
| **企业级任务**（无人值守、高可靠） | 🔲 待开发 | 需要持久化、状态管理 |

**已适配站点**：百度搜索、GitHub 登录

**端到端演示**：
```
用户: 帮我在百度搜索 Python 教程
AI:   调用 run_task("帮我在百度搜索 Python 教程")
      → Agent: 截图→查技能→执行脚本→返回结果
```

## 架构

```
┌─────────────────────────────────────────────────────────┐
│  MCP 协议层（8 个工具）                                    │
│  run_task │ browse_skills │ run_script │ analyze_page   │
└──────┬──────────┬──────────┬────────────┬───────────────┘
       │          │          │            │
       ▼          ▼          ▼            ▼
  ┌─────────┐ ┌────────┐ ┌──────────┐ ┌────────┐
  │  Skill  │ │ Script │ │  Agent   │ │ Vision │
  │ Library │ │ Engine │ │  Loop    │ │ Module │
  └─────────┘ └────┬───┘ └──────────┘ └────────┘
                   │
       ┌───────────┼───────────┐
       ▼           ▼           ▼
 ┌──────────┐ ┌────────┐ ┌─────────┐
 │ Controls │ │ Layer1 │ │ Layer3  │
 │ (控件层)  │ │(原语层) │ │(域配置) │
 └──────────┘ └────────┘ └─────────┘
                   │
                   ▼
 ┌─────────────────────────────────┐
 │  Playwright / CloakBrowser      │
 └─────────────────────────────────┘
```

| 模块 | 职责 | 状态 |
|------|------|------|
| **Agent 循环** | OBSERVE→PLAN→ACT 自主执行 | ✅ |
| **脚本引擎** | 受限沙箱执行 AI 生成的 Python 脚本 | ✅ |
| **控件层** | `smart_login`, `smart_search` 等 15 个高级函数 | ✅ |
| **标准脚本库** | `.py` 范例 + `.md` 说明 + `skills.yaml` 索引 | ✅ |
| **视觉模块** | 截图 + 多模态 LLM 理解页面 | ✅ |
| **Layer 1 — 原语层** | `goto`, `click`, `fill`, `screenshot` | ✅ |
| **Layer 3 — 域配置** | YAML 选择器 + 自愈写回 | ✅ |
| **事件钩子** | EventBus + 7 种标准事件 | ✅ |
| **插件系统** | SkillBase 抽象类 + skills.yaml 声明式配置 | ✅ |
| **CLI** | `browser-agent serve/run/doctor` | ✅ |

## MCP 工具列表（8 个）

| 工具 | 说明 |
|------|------|
| `run_task` | 自然语言驱动的自主 Agent 循环 |
| `browse_skills` | 按关键词或 URL 查找技能库 |
| `get_skill` | 获取技能源码和说明文档 |
| `run_script` | 在受限沙箱中执行 Python 脚本 |
| `analyze_page` | 截图 + 多模态 LLM 分析页面（需 API Key） |
| `browser_launch` | 启动 Chromium 浏览器 |
| `screenshot` | 截取当前页面截图 |
| `ping` | 健康检查 |

## 快速开始

```bash
# 1. 克隆仓库
git clone https://github.com/zceeeeee/agentic-playwright-mcp.git
cd agentic-playwright-mcp

# 2. 一键安装（依赖 + Playwright 浏览器）
make dev

# 3. 复制环境变量
cp .env.example .env

# 4. 启动
make run
```

## CLI 工具

```bash
# 启动 MCP 服务
browser-agent serve

# 单次执行任务（调试用）
browser-agent run "帮我在百度搜索 Python 教程" --max-steps 5

# 无头模式
browser-agent run "截图当前页面" --headless

# 检查环境
browser-agent doctor
```

## 插件化技能

添加新技能只需两步：

1. 在 `skills.yaml` 中声明元信息
2. 在 `src/skill_library/domains/` 或 `interactions/` 中放置 `.py` 文件

```yaml
# skills.yaml
skills:
  - id: my_site
    name: 我的网站
    type: domain
    triggers: ["我的网站", "mysite"]
    url_patterns: ["mysite.com"]
    description: 我的网站适配器
```

```python
# src/skill_library/domains/my_site.py
def run(keyword: str):
    """在我的网站搜索关键词。"""
    goto("https://www.mysite.com")
    fill("#search", keyword)
    click("#search-btn")
    wait_for_navigation()
```

## 脚本引擎可用函数

```python
# 导航
goto("https://example.com")
go_back()

# 元素操作（支持多个备选选择器）
click("#button", ".fallback-btn")
fill("#input", "hello")

# 域配置驱动（带自愈）
smart_click("search_button", domain="baidu")
smart_fill("search_input", "Python 教程", domain="baidu")

# 组合操作
smart_login("github", "user", "pass")
smart_search("baidu", "Python 教程")
smart_fill_form("example", {"name": "张三", "email": "test@test.com"})

# 等待
wait_for_navigation(timeout=10)
wait_for_element("#result", timeout=10)
wait(2.0)

# 页面信息
url = get_url()
title = get_title()
text = get_text()
screenshot("page.png")
```

## CloakBrowser 反检测引擎

```bash
pip install -e ".[stealth]"
USE_CLOAKBROWSER=true make run
```

| 检测服务 | Playwright | CloakBrowser |
|---------|-----------|-------------|
| reCAPTCHA v3 | 0.1 (bot) | **0.9** (human) |
| Cloudflare Turnstile | FAIL | **PASS** |
| FingerprintJS | DETECTED | **PASS** |

## 文档

```bash
pip install -e ".[docs]"
make docs        # 启动本地文档服务器
make docs-build  # 构建静态文档
```

## 项目结构

```
agentic-playwright-mcp/
├── src/
│   ├── server.py                     # MCP 入口（8 个工具）
│   ├── cli.py                        # CLI (serve/run/doctor)
│   ├── core/
│   │   ├── agent_loop.py             # Agent 循环引擎
│   │   ├── script_engine.py          # 脚本执行引擎
│   │   ├── browser_manager.py        # 双引擎浏览器管理
│   │   ├── event_bus.py              # 事件钩子系统
│   │   └── vision.py                 # 视觉模块
│   ├── layer_1/actions.py            # 原子操作
│   ├── layer_2/controls.py           # 高级控件函数
│   ├── layer_3/                      # 域配置 + 自愈
│   └── skill_library/                # 标准脚本库
│       ├── skill_base.py             # SkillBase 抽象类
│       ├── skills.yaml               # 声明式配置
│       ├── domains/                  # 站点适配器
│       ├── interactions/             # 通用模板
│       └── guides/                   # 说明文档
├── domains/                          # 站点选择器配置
├── tests/                            # 475 个测试，全部通过
├── docs/                             # MkDocs 文档
└── examples/                         # 示例脚本
```

## 开发

```bash
make dev      # 安装依赖
make test     # 跑测试（475 个）
make lint     # 代码检查
make format   # 自动修复
make clean    # 清理缓存
make docs     # 启动文档服务器
```

## License

MIT
