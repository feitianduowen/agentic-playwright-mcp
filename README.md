# Agentic Playwright MCP

轻量级桌面自动化底座 —— 基于 Playwright 的 MCP Server，通过三层进化架构为 AI Agent 提供浏览器操控能力。

## 三层架构

```
Layer 3: Domains (站点经验)     ← domains/*.yaml，选择器数据化 + 自愈写回
Layer 2: Skills  (肌肉记忆)     ← 可复用操作序列（预留）
Layer 1: Helpers (原语)          ← 单步原子操作：点击、输入、截图…
```

| 层级 | 职责 | 当前状态 |
|------|------|----------|
| **Layer 1 — Helpers** | 单步原语：`navigate`, `smart_click`, `screenshot` 等 | 已实现 |
| **Layer 2 — Skills** | 将多个原语编排为可复用序列 | 预留接口 |
| **Layer 3 — Domains** | 加载站点 YAML 配置；选择器失败时自动提升优先级 | 已实现 |

## 安装

```bash
# 1. 克隆仓库
git clone <repo-url>
cd agentic-playwright-mcp

# 2. 安装项目（含依赖）
pip install -e .

# 3. 安装 Chromium 浏览器
playwright install chromium
```

## 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入 API Key（如需调用 LLM 视觉能力）
# OPENAI_API_KEY=sk-xxx
```

## 启动

```bash
# 方式一：模块启动
python -m src.server

# 方式二：CLI 入口
agentic-playwright-mcp
```

启动后，MCP Server 将在 **stdio** 上监听，等待客户端连接。

## MCP 工具列表

| 工具名 | 说明 |
|--------|------|
| `ping` | 健康检查，返回 `pong` |
| `browser_launch` | 启动 Chromium 浏览器实例 |
| `navigate` | 导航到指定 URL |
| `smart_click` | 通过 Domain YAML 中的选择器点击元素 |
| `screenshot` | 截取当前页面截图 |

## 在 Claude Desktop 中配置

编辑 Claude Desktop 的 MCP 配置文件：

```json
{
  "mcpServers": {
    "agentic-playwright": {
      "command": "python",
      "args": ["-m", "src.server"],
      "cwd": "/path/to/agentic-playwright-mcp"
    }
  }
}
```

重启 Claude Desktop 后，上方工具列表将自动出现在 Claude 的可用工具中。

## 选择器数据化示例

所有选择器均存放在 `domains/*.yaml` 中，严禁在 Python 代码里硬编码：

```yaml
name: baidu
base_url: https://www.baidu.com
locators:
  search_input:
    css:
      - "#kw"
      - "input[name='wd']"
      - ".s_ipt"
    xpath:
      - "//input[@id='kw']"
      - "//input[@name='wd']"
```

当某个选择器在运行时成功定位元素后，`config_updater` 会将其自动提升到列表首位，实现 **自愈** 效果。
