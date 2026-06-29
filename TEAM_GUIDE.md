# 团队开发指南

> 本文档面向新加入的组员，帮助你快速理解项目全貌并开始贡献代码。

---

## 一、这个项目在做什么？

**一句话概括**：让 AI Agent 能通过写 Python 脚本来控制浏览器。

传统做法是 AI 逐个调用工具（点击、输入、截图……），每一步都需要 LLM 推理。
我们的做法是 **AI 直接写一段 Python 脚本**，脚本引擎在沙箱里执行。

```
传统方式:  AI → 调工具1 → 等结果 → 调工具2 → 等结果 → ...（慢、贵）
我们方式:  AI → 写一段脚本 → 脚本引擎一次性执行（快、可复用）
```

**核心价值**：用得越多，系统越聪明。成功的脚本会自动保存，下次相同任务直接复用。

---

## 二、架构全景

```
用户（自然语言）
    │
    ▼
┌─────────────────────────────────────────────┐
│  MCP Server (server.py)                     │  ← 对外暴露 9 个工具
│  Claude Desktop / 任何 MCP 客户端 连接这里    │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│  Agent Loop (agent_loop.py)                 │  ← 自主决策引擎
│  OBSERVE → PLAN → ACT → OBSERVE → ...       │
│                                             │
│  OBSERVE: 截图 + 视觉分析当前页面             │
│  PLAN:    查技能库 → 查经验库 → 生成脚本      │
│  ACT:     在沙箱中执行脚本                    │
└─────────────┬───────────────────────────────┘
              │
    ┌─────────┼─────────┐
    ▼         ▼         ▼
┌────────┐┌────────┐┌────────┐
│Layer 2 ││经验系统 ││视觉模块 │
│Controls││Experience││Vision │
│高级组合 ││脚本复用  ││LLM分析 │
└───┬────┘└────────┘└────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│  Layer 1 — Actions (actions.py)             │
│  goto / click / fill / screenshot           │
│  多选择器自愈：按优先级依次尝试                │
└─────────────┬───────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────┐
│  Layer 3 — Domain Config (domains/*.yaml)   │
│  每个网站的元素选择器配置                      │
│  自愈机制：备用选择器成功后自动提升优先级        │
└─────────────┬───────────────────────────────┘
              │
              ▼
        Playwright / CloakBrowser
              │
              ▼
          真实浏览器
```

---

## 三、核心模块速查

| 模块 | 文件 | 一句话职责 |
|------|------|-----------|
| **MCP 入口** | `src/server.py` | 注册 9 个工具，对接 MCP 客户端 |
| **CLI** | `src/cli.py` | `serve`/`run`/`doctor`/`gui` 四个子命令 |
| **浏览器管理** | `src/core/browser_manager.py` | 单例，Playwright/CloakBrowser 双引擎切换 |
| **脚本引擎** | `src/core/script_engine.py` | 沙箱执行 AI 生成的 Python 脚本 |
| **Agent 循环** | `src/core/agent_loop.py` | OBSERVE→PLAN→ACT 状态机 |
| **脚本生成** | `src/core/script_generator.py` | 自然语言意图解析 → 脚本模板 |
| **视觉模块** | `src/core/vision.py` | 截图 + Claude/GPT-4V 分析页面 |
| **经验系统** | `src/core/experience.py` | 脚本复用 + 选择器经验 + 站点知识 |
| **事件总线** | `src/core/event_bus.py` | 中央化钩子系统（before/after） |
| **错误恢复** | `src/core/recovery.py` | 弹窗/超时/导航失败的自动恢复策略 |
| **原语层** | `src/layer_1/actions.py` | goto/click/fill/screenshot 原子操作 |
| **控件层** | `src/layer_2/controls.py` | smart_click/fill/login/search 高级组合 |
| **域配置加载** | `src/layer_3/domain_loader.py` | YAML 加载 + Pydantic 校验 |
| **自愈写入** | `src/layer_3/config_updater.py` | 选择器优先级提升（写回 YAML） |
| **技能库** | `src/skill_library/` | 预置技能（搜索/登录/表单/分页） |

---

## 四、关键设计模式（必须理解）

### 1. 自愈选择器

```yaml
# domains/baidu.yaml
search_input:
  css:
    - "#kw"              # 第一优先级
    - "input[name='wd']" # 第二优先级
    - ".s_ipt"           # 第三优先级
```

`do_click()` 按顺序尝试每个选择器。如果 `#kw` 失败但 `input[name='wd']` 成功了，
`update_selector_priority()` 会把 `input[name='wd']` 提升到第一位并写回 YAML。
**下次再访问百度，就直接用成功的那个了。**

### 2. 沙箱脚本执行

AI 生成的代码在受限命名空间中运行：
- ✅ 可用：`goto()`, `click()`, `fill()`, `smart_search()`, `print()`, `log()`
- ❌ 禁止：`import`, `open()`, `os.system()`, `eval()`, 网络请求

白名单在 `script_engine.py` 的 `_SAFE_BUILTINS` 和 `_build_namespace()` 中定义。

### 3. 事件总线

所有操作都通过 EventBus 发射事件，支持钩子注入：

```python
bus = get_event_bus()

@bus.on("click", phase="before")
def log_click(event):
    print(f"即将点击: {event.data['selector_list']}")

@bus.on("navigate", phase="after")
def track_nav(event):
    print(f"已导航到: {event.result}")
```

### 4. Agent 循环状态机

```
OBSERVE ──→ PLAN ──→ ACT ──→ OBSERVE → ...
   │           │        │
   │           │        └─ 失败且是选择器错误 → HEAL（视觉 fallback）
   │           │        └─ 其他失败 → FAILED
   │           │
   │           └─ 查技能库 → 命中 → 用技能源码
   │           └─ 查经验库 → 命中 → 复用脚本
   │           └─ 都没命中 → 生成临时脚本
   │
   └─ 视觉分析（降级到 URL/title）
```

---

## 五、开发环境搭建

```bash
# 1. 克隆项目
git clone <repo-url>
cd agentic-playwright-mcp

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS/Linux

# 3. 安装依赖
pip install -e .
pip install -e ".[dev]"         # 开发依赖（pytest, ruff）
playwright install chromium     # 安装浏览器

# 4. 配置环境变量
copy .env.example .env
# 编辑 .env，填入 ANTHROPIC_API_KEY 或 OPENAI_API_KEY（视觉功能需要）

# 5. 检查环境
browser-agent doctor
```

---

## 六、常用开发命令

```bash
# 启动 MCP 服务（对接 Claude Desktop）
browser-agent serve

# 单次执行任务
browser-agent run "帮我在百度搜索 Python 教程"

# 启动 Web GUI
browser-agent gui --port 8081

# 跑测试
pytest tests/ -v

# 代码检查
ruff check src/
ruff format src/
```

---

## 七、当前完成度

### ✅ 已完成

| 模块 | 状态 | 说明 |
|------|------|------|
| MCP Server + 9 个工具 | ✅ | 完整可用 |
| 浏览器双引擎 | ✅ | Playwright + CloakBrowser |
| 脚本沙箱引擎 | ✅ | 受限命名空间 + 白名单 |
| Agent 循环 | ✅ | OBSERVE→PLAN→ACT 状态机 |
| 自愈选择器 | ✅ | 多选择器降级 + 优先级自动提升 |
| 事件总线 | ✅ | before/after 钩子 + 生命周期管理 |
| 视觉模块 | ✅ | Claude Vision + GPT-4V |
| 经验系统 | ✅ | 脚本复用 + 选择器经验 + 站点知识 |
| 脚本生成器 | ✅ | 10 种意图类型 + 18+ 站点支持 |
| 技能库 | ✅ | 6 个预置技能 + 注册表 |
| CLI + GUI | ✅ | serve/run/doctor/gui |
| 域配置 | ✅ | 19 个站点的 YAML 配置 |
| 测试 | ✅ | 基础覆盖 |

### ⚠️ 待完善

| 模块 | 优先级 | 说明 |
|------|--------|------|
| **Layer 2 技能扩展** | 🔴 高 | 当前只有 6 个预置技能，需要更多站点/交互模式 |
| **域配置覆盖** | 🔴 高 | 19 个站点的选择器需要实际验证和补充 |
| **Agent 推理能力** | 🟡 中 | 当前是模板匹配，复杂任务需要更强的推理 |
| **错误恢复集成** | 🟡 中 | recovery.py 已实现但未完全集成到 Agent Loop |
| **多标签页支持** | 🟡 中 | 当前只操作单页面 |
| **测试覆盖率** | 🟢 低 | 需要更多集成测试和端到端测试 |
| **文档完善** | 🟢 低 | API 文档、架构文档 |

---

## 八、如何贡献代码

### 场景 1：添加新站点支持

这是最容易上手的任务。

**步骤**：

1. 创建域配置 `domains/xxx.yaml`：
```yaml
name: xxx
base_url: https://xxx.com
locators:
  search_input:
    css:
      - "#search-box"
      - "input[type='search']"
    xpath:
      - "//input[@id='search-box']"
  search_button:
    css:
      - "#search-btn"
      - "button[type='submit']"
```

2. 在 `script_generator.py` 的 `SITE_META` 中添加站点元数据：
```python
"xxx": {"url": "https://xxx.com", "name": "XXX"},
```

3. 如果站点有特殊交互模式（如 JS 注入），在 `_gen_search()` 中添加分支。

4. 在 `skill_library/domains/` 下创建技能文件（可选）。

5. 运行测试验证：`browser-agent run "在xxx搜索关键词"`

---

### 场景 2：添加新技能

**步骤**：

1. 创建技能源码 `src/skill_library/<category>/xxx.py`：
```python
"""XXX 站点技能。"""

def run(keyword: str = ""):
    """在 XXX 搜索关键词。"""
    goto("https://xxx.com")
    wait_for_navigation()
    smart_fill("search_input", keyword, domain="xxx")
    smart_click("search_button", domain="xxx")
    wait_for_navigation()
    text = get_text()
    print(text[:2000])
```

2. 创建使用指南 `src/skill_library/guides/how_to_xxx.md`（可选）。

3. 在 `src/skill_library/registry.json` 中注册：
```json
{
  "id": "xxx",
  "name": "XXX 搜索",
  "type": "domain",
  "triggers": ["xxx", "搜索"],
  "url_patterns": ["xxx.com"],
  "file": "search/xxx.py",
  "function": "run",
  "description": "在 XXX 搜索关键词"
}
```

---

### 场景 3：扩展控件层函数

当你需要封装新的交互模式（如拖拽、多选、富文本编辑）：

1. 在 `src/layer_2/controls.py` 中添加函数：
```python
def drag_drop(source: str, target: str, domain: str = "default") -> dict:
    """拖拽元素。"""
    page = get_browser_manager().get_page()
    # 实现逻辑...
    return {"success": True}
```

2. 在 `get_controls_exports()` 中注册，脚本引擎就能调用了：
```python
def get_controls_exports() -> Dict[str, Any]:
    return {
        # ... 已有函数 ...
        "drag_drop": drag_drop,
    }
```

---

### 场景 4：集成错误恢复

`recovery.py` 已实现但未完全集成到 Agent Loop。需要：

1. 在 `agent_loop.py` 的 `_do_act()` 中，失败时调用 RecoveryManager：
```python
from src.core.recovery import RecoveryManager

recovery = RecoveryManager(bm.get_page())
action = recovery.handle_error(Exception(step.error), context=step.action)
if recovery.execute_recovery(action):
    # 恢复成功，重试
    return self._do_act(step)
```

2. 添加更多恢复策略（如 CAPTCHA 检测、登录态过期）。

---

## 九、代码规范

- **语言**：Python 3.11+，使用 type hints
- **格式化**：`ruff format`（88 字符行宽）
- **Lint**：`ruff check`（E/F/I/W 规则）
- **注释**：中文注释 + Google 风格 docstring
- **测试**：`pytest`，文件名 `test_*.py`
- **提交**：`feat: xxx` / `fix: xxx` / `docs: xxx` / `refactor: xxx`

---

## 十、文件速查

```
agentic-playwright-mcp/
├── src/
│   ├── server.py              # MCP 入口，9 个工具定义
│   ├── cli.py                 # CLI 子命令
│   ├── sdk.py                 # Python SDK
│   ├── config.py              # .env 配置加载
│   ├── config_manager.py      # 配置管理（交互式 setup）
│   ├── logging.py             # 结构化日志
│   ├── core/
│   │   ├── agent_loop.py      # ⭐ Agent 循环（OBSERVE→PLAN→ACT）
│   │   ├── script_engine.py   # ⭐ 脚本沙箱引擎
│   │   ├── script_generator.py # 意图解析 + 脚本生成
│   │   ├── experience.py      # 经验进化系统
│   │   ├── browser_manager.py # 浏览器生命周期管理
│   │   ├── event_bus.py       # 事件钩子系统
│   │   ├── recovery.py        # 错误恢复策略
│   │   ├── vision.py          # 视觉模块（LLM 分析）
│   │   └── script_store.py    # 脚本存储
│   ├── layer_1/
│   │   └── actions.py         # 原子操作（goto/click/fill/screenshot）
│   ├── layer_2/
│   │   ├── controls.py        # ⭐ 高级控件（smart_click/fill/login）
│   │   ├── skill_schema.py    # 技能数据模型
│   │   └── skill_loader.py    # 技能加载器
│   ├── layer_3/
│   │   ├── domain_loader.py   # YAML 加载 + Pydantic 校验
│   │   └── config_updater.py  # 选择器优先级自愈写入
│   ├── skill_library/
│   │   ├── registry.json      # 技能注册表
│   │   ├── skill_base.py      # 技能基类
│   │   ├── domains/           # 站点技能（baidu/github/google/...）
│   │   ├── interactions/      # 交互技能（login/search/form/pagination）
│   │   └── guides/            # 使用指南（Markdown）
│   └── gui/
│       └── app.py             # Web GUI（Flask）
├── domains/                   # 站点选择器配置（19 个 YAML）
├── skills/                    # YAML 格式技能定义
├── workspace/                 # 经验存储（运行时生成）
│   ├── scripts/               # 保存的成功脚本
│   ├── selectors/             # 选择器经验
│   └── knowledge/             # 站点知识
├── tests/                     # 测试文件
├── pyproject.toml             # 项目配置
├── .env.example               # 环境变量模板
└── TEAM_GUIDE.md              # 本文档
```

---

## 十一、常见问题

**Q: 运行时报 "Browser not launched"**
A: 需要先调用 `browser_launch` 工具，或用 CLI 的 `browser-agent run` 会自动启动。

**Q: 视觉功能不工作**
A: 需要在 `.env` 中设置 `ANTHROPIC_API_KEY` 或 `OPENAI_API_KEY`。

**Q: 如何调试脚本？**
A: 用 `browser-agent run --headed --slow-mo 500 "任务描述"` 可以看到浏览器操作过程。

**Q: 如何添加新的 MCP 工具？**
A: 在 `server.py` 中用 `@mcp.tool()` 装饰器定义函数即可。

**Q: CloakBrowser 和 Playwright 有什么区别？**
A: Playwright 是官方引擎；CloakBrowser 是反检测引擎，能绕过 reCAPTCHA/Cloudflare 等检测。通过 `USE_CLOAKBROWSER=true` 环境变量切换。

---

## 十二、推荐阅读顺序

1. **本文档** — 理解全貌
2. `src/server.py` — 了解对外接口
3. `src/layer_1/actions.py` — 理解原子操作和自愈逻辑
4. `src/layer_2/controls.py` — 理解高级组合和域配置驱动
5. `src/core/script_engine.py` — 理解沙箱执行
6. `src/core/agent_loop.py` — 理解 Agent 自主决策
7. `domains/example_baidu.yaml` — 理解域配置格式
8. `src/skill_library/registry.json` — 理解技能注册机制

有问题随时问！🚀
