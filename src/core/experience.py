"""
经验进化模块 —— 记录、积累、复用自动化经验。

参考 Browser Harness 的 agent-workspace 设计：
- 成功的脚本自动保存，下次相同任务直接复用
- 选择器成功/失败记录跨任务共享
- Agent 发现的非显而易见知识自动沉淀为技能

核心理念："用得越多，系统越聪明。"
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


# ---------------------------------------------------------------------------
# 数据模型
# ---------------------------------------------------------------------------


@dataclass
class SelectorExperience:
    """选择器经验记录。"""

    selector: str
    site: str
    element: str
    success_count: int = 0
    fail_count: int = 0
    last_success: float = 0.0
    last_fail: float = 0.0

    @property
    def reliability(self) -> float:
        """可靠性评分 (0.0 - 1.0)。"""
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.5
        return self.success_count / total


@dataclass
class ScriptRecord:
    """脚本记录。"""

    id: str
    task: str
    script: str
    site: str = ""
    created_at: float = 0.0
    last_used_at: float = 0.0
    use_count: int = 0
    success_count: int = 0
    tags: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.use_count == 0:
            return 0.0
        return self.success_count / self.use_count


@dataclass
class SiteKnowledge:
    """站点知识（类似 Browser Harness 的 domain-skills）。"""

    site: str
    url: str = ""
    selectors: dict[str, list[str]] = field(default_factory=dict)
    gotchas: list[str] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    last_updated: float = 0.0


# ---------------------------------------------------------------------------
# 经验管理器
# ---------------------------------------------------------------------------


class ExperienceManager:
    """经验管理器 —— 记录、查询、复用自动化经验。

    类似 Browser Harness 的 agent-workspace，但结构化存储：
    - scripts/: 成功的脚本
    - selectors/: 选择器经验
    - knowledge/: 站点知识
    """

    def __init__(self, workspace_dir: str | Path | None = None) -> None:
        if workspace_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            workspace_dir = project_root / "workspace"

        self._workspace = Path(workspace_dir)
        self._scripts_dir = self._workspace / "scripts"
        self._selectors_dir = self._workspace / "selectors"
        self._knowledge_dir = self._workspace / "knowledge"

        # 创建目录
        self._scripts_dir.mkdir(parents=True, exist_ok=True)
        self._selectors_dir.mkdir(parents=True, exist_ok=True)
        self._knowledge_dir.mkdir(parents=True, exist_ok=True)

        # 内存缓存
        self._selector_cache: dict[str, SelectorExperience] = {}
        self._script_cache: dict[str, ScriptRecord] = {}
        self._knowledge_cache: dict[str, SiteKnowledge] = {}

        # 加载已有经验
        self._load_all()

    # -------------------------------------------------------------------
    # 脚本管理
    # -------------------------------------------------------------------

    def save_script(self, task: str, script: str, site: str = "", tags: list[str] | None = None) -> ScriptRecord:
        """保存成功执行的脚本。"""
        script_id = self._generate_id(task)

        if script_id in self._script_cache:
            record = self._script_cache[script_id]
            record.script = script
            record.last_used_at = time.time()
        else:
            record = ScriptRecord(
                id=script_id,
                task=task,
                script=script,
                site=site,
                created_at=time.time(),
                last_used_at=time.time(),
                tags=tags or [],
            )
            self._script_cache[script_id] = record

        # 保存到文件
        script_path = self._scripts_dir / f"{script_id}.py"
        script_path.write_text(script, encoding="utf-8")

        self._save_scripts_index()
        return record

    def find_script(self, task: str) -> ScriptRecord | None:
        """查找匹配的脚本（精确匹配或相似匹配）。"""
        script_id = self._generate_id(task)
        if script_id in self._script_cache:
            return self._script_cache[script_id]

        # 相似匹配：检查关键词重叠
        task_words = set(task.lower().split())
        best_match = None
        best_score = 0

        for record in self._script_cache.values():
            record_words = set(record.task.lower().split())
            overlap = len(task_words & record_words)
            if overlap > best_score and overlap >= 2:
                best_score = overlap
                best_match = record

        return best_match

    def record_script_usage(self, script_id: str, success: bool) -> None:
        """记录脚本使用结果。"""
        if script_id in self._script_cache:
            record = self._script_cache[script_id]
            record.use_count += 1
            record.last_used_at = time.time()
            if success:
                record.success_count += 1
            self._save_scripts_index()

    # -------------------------------------------------------------------
    # 选择器经验
    # -------------------------------------------------------------------

    def record_selector_success(self, site: str, element: str, selector: str) -> None:
        """记录选择器成功。"""
        key = f"{site}:{element}:{selector}"
        if key not in self._selector_cache:
            self._selector_cache[key] = SelectorExperience(
                selector=selector, site=site, element=element
            )
        exp = self._selector_cache[key]
        exp.success_count += 1
        exp.last_success = time.time()
        self._save_selector_experience(site)

    def record_selector_failure(self, site: str, element: str, selector: str) -> None:
        """记录选择器失败。"""
        key = f"{site}:{element}:{selector}"
        if key not in self._selector_cache:
            self._selector_cache[key] = SelectorExperience(
                selector=selector, site=site, element=element
            )
        exp = self._selector_cache[key]
        exp.fail_count += 1
        exp.last_fail = time.time()
        self._save_selector_experience(site)

    def get_best_selectors(self, site: str, element: str) -> list[str]:
        """获取按可靠性排序的选择器列表。"""
        experiences = [
            exp for exp in self._selector_cache.values()
            if exp.site == site and exp.element == element
        ]
        experiences.sort(key=lambda e: e.reliability, reverse=True)
        return [exp.selector for exp in experiences]

    # -------------------------------------------------------------------
    # 站点知识
    # -------------------------------------------------------------------

    def add_knowledge(self, site: str, gotcha: str = "", pattern: str = "") -> None:
        """添加站点知识（类似 Browser Harness 的 domain-skills）。"""
        if site not in self._knowledge_cache:
            self._knowledge_cache[site] = SiteKnowledge(
                site=site, last_updated=time.time()
            )

        knowledge = self._knowledge_cache[site]
        if gotcha and gotcha not in knowledge.gotchas:
            knowledge.gotchas.append(gotcha)
        if pattern and pattern not in knowledge.patterns:
            knowledge.patterns.append(pattern)
        knowledge.last_updated = time.time()

        self._save_knowledge(site)

    def get_knowledge(self, site: str) -> SiteKnowledge | None:
        """获取站点知识。"""
        return self._knowledge_cache.get(site)

    # -------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------

    def _generate_id(self, task: str) -> str:
        return hashlib.md5(task.encode("utf-8")).hexdigest()[:12]

    def _load_all(self) -> None:
        """加载所有经验数据。"""
        self._load_scripts_index()
        self._load_all_selectors()
        self._load_all_knowledge()

    def _load_scripts_index(self) -> None:
        index_path = self._scripts_dir / "index.json"
        if not index_path.exists():
            return
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("scripts", []):
                record = ScriptRecord(**item)
                self._script_cache[record.id] = record
        except (json.JSONDecodeError, KeyError):
            pass

    def _save_scripts_index(self) -> None:
        index_path = self._scripts_dir / "index.json"
        data = {
            "scripts": [asdict(r) for r in self._script_cache.values()],
            "updated_at": time.time(),
        }
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_all_selectors(self) -> None:
        for path in self._selectors_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("experiences", []):
                    exp = SelectorExperience(**item)
                    key = f"{exp.site}:{exp.element}:{exp.selector}"
                    self._selector_cache[key] = exp
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_selector_experience(self, site: str) -> None:
        site_exps = [
            exp for exp in self._selector_cache.values()
            if exp.site == site
        ]
        path = self._selectors_dir / f"{site}.json"
        data = {
            "site": site,
            "experiences": [asdict(e) for e in site_exps],
            "updated_at": time.time(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_all_knowledge(self) -> None:
        for path in self._knowledge_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                knowledge = SiteKnowledge(**data)
                self._knowledge_cache[knowledge.site] = knowledge
            except (json.JSONDecodeError, KeyError):
                pass

    def _save_knowledge(self, site: str) -> None:
        knowledge = self._knowledge_cache.get(site)
        if not knowledge:
            return
        path = self._knowledge_dir / f"{site}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(knowledge), f, ensure_ascii=False, indent=2)

    # -------------------------------------------------------------------
    # 统计
    # -------------------------------------------------------------------

    def get_stats(self) -> dict:
        """获取经验统计。"""
        return {
            "scripts": len(self._script_cache),
            "selector_experiences": len(self._selector_cache),
            "sites_with_knowledge": len(self._knowledge_cache),
            "workspace_dir": str(self._workspace),
        }


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_instance: ExperienceManager | None = None


def get_experience_manager(workspace_dir: str | Path | None = None) -> ExperienceManager:
    global _instance
    if _instance is None:
        _instance = ExperienceManager(workspace_dir=workspace_dir)
    return _instance


def reset_experience_manager() -> None:
    global _instance
    _instance = None
