"""
技能注册与查找 -- 管理标准脚本库的索引。

AI 可以通过关键词或 URL 模式查找匹配的技能，
获取技能源码和说明文档。

数据来源: skills.yaml (元数据) + skill_base.SkillMeta (数据模型)
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

import yaml

from .skill_base import SkillBase, SkillMeta

# ---------------------------------------------------------------------------
# 文件映射 -- 记录每个技能对应的源码文件和入口函数
# ---------------------------------------------------------------------------


@dataclass
class SkillFileMapping:
    """技能文件映射 -- 从 skills.yaml 的 sources 段加载。

    Attributes:
        id: 技能 ID，与 SkillMeta.id 对应。
        file: 源码文件路径（相对于 library_dir）。
        entry: 入口函数名或类名。
    """

    id: str
    file: str
    entry: str = "run"


# ---------------------------------------------------------------------------
# 技能详情
# ---------------------------------------------------------------------------


@dataclass
class SkillDetail:
    """技能详情（元数据 + 源码 + 说明文档 + 实例）。"""

    meta: SkillMeta
    file_mapping: Optional[SkillFileMapping] = None
    source_code: str = ""
    guide: str = ""
    instance: Optional[SkillBase] = None


# ---------------------------------------------------------------------------
# 技能注册表
# ---------------------------------------------------------------------------


class SkillRegistry:
    """技能注册表 -- 管理所有技能的索引和查找。

    使用方式::

        registry = SkillRegistry(library_dir="src/skill_library")
        registry.load_from_yaml()   # 自动加载 skills.yaml

        # 搜索
        results = registry.search(query="百度")
        results = registry.search(url="https://www.baidu.com")

        # 获取详情
        detail = registry.get_detail("domain/baidu_search")
    """

    def __init__(self, library_dir: str | Path | None = None) -> None:
        self._metas: Dict[str, SkillMeta] = {}
        self._file_mappings: Dict[str, SkillFileMapping] = {}
        self._instances: Dict[str, SkillBase] = {}
        self._library_dir: Optional[Path] = Path(library_dir) if library_dir else None

    # -------------------------------------------------------------------
    # 注册
    # -------------------------------------------------------------------

    def register(
        self, meta: SkillMeta, file_mapping: SkillFileMapping | None = None
    ) -> None:
        """注册一个技能。

        Args:
            meta: 技能元数据。
            file_mapping: 可选的文件映射，用于定位源码和实例化。
        """
        self._metas[meta.id] = meta
        if file_mapping:
            self._file_mappings[meta.id] = file_mapping

    def register_many(
        self, items: list[tuple[SkillMeta, SkillFileMapping | None]]
    ) -> None:
        """批量注册技能。"""
        for meta, mapping in items:
            self.register(meta, mapping)

    # -------------------------------------------------------------------
    # 加载
    # -------------------------------------------------------------------

    def load_from_yaml(self, yaml_path: str | Path | None = None) -> None:
        """从 skills.yaml 加载技能索引。

        Args:
            yaml_path: skills.yaml 文件路径。若为 None，自动在 library_dir 下查找。
        """
        if yaml_path is None:
            if self._library_dir is None:
                return
            yaml_path = self._library_dir / "skills.yaml"

        path = Path(yaml_path)
        if not path.exists():
            return

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 构建 sources 映射: id -> SkillFileMapping
        sources_map: Dict[str, SkillFileMapping] = {}
        for src in data.get("sources", []):
            fm = SkillFileMapping(
                id=src["id"],
                file=src["file"],
                entry=src.get("entry", "run"),
            )
            sources_map[fm.id] = fm

        # 加载技能元数据
        for item in data.get("skills", []):
            meta = SkillMeta(
                id=item["id"],
                name=item["name"],
                type=item["type"],
                triggers=item.get("triggers", []),
                url_patterns=item.get("url_patterns", []),
                description=item.get("description", ""),
                version=item.get("version", "1.0.0"),
            )
            file_mapping = sources_map.get(meta.id)
            self.register(meta, file_mapping)

    # -------------------------------------------------------------------
    # 查找
    # -------------------------------------------------------------------

    def search(
        self, query: str | None = None, url: str | None = None
    ) -> list[SkillMeta]:
        """按关键词或 URL 查找匹配的技能。

        Args:
            query: 搜索关键词（匹配 triggers 列表）。
            url: 要匹配的 URL（匹配 url_patterns 列表）。

        Returns:
            匹配的 SkillMeta 列表。
        """
        results: list[SkillMeta] = []
        for meta in self._metas.values():
            if query and self._matches_query(meta, query):
                results.append(meta)
            elif url and self._matches_url(meta, url):
                results.append(meta)
        return results

    def get(self, skill_id: str) -> SkillMeta | None:
        """按 ID 获取技能元数据。"""
        return self._metas.get(skill_id)

    def get_detail(self, skill_id: str) -> SkillDetail | None:
        """获取技能详情（含源码、说明文档和实例）。

        Args:
            skill_id: 技能 ID。

        Returns:
            SkillDetail 或 None。
        """
        meta = self._metas.get(skill_id)
        if meta is None:
            return None

        detail = SkillDetail(meta=meta)
        file_mapping = self._file_mappings.get(skill_id)
        detail.file_mapping = file_mapping

        if self._library_dir and file_mapping and file_mapping.file:
            # 读取源码
            source_path = self._library_dir / file_mapping.file
            if source_path.exists():
                detail.source_code = source_path.read_text(encoding="utf-8")

            # 读取说明文档
            guide_path = self._infer_guide_path(file_mapping)
            if guide_path and guide_path.exists():
                detail.guide = guide_path.read_text(encoding="utf-8")

        # 尝试获取或实例化技能对象
        detail.instance = self._get_or_create_instance(skill_id)

        return detail

    def list_all(self) -> list[SkillMeta]:
        """列出所有已注册的技能元数据。"""
        return list(self._metas.values())

    # -------------------------------------------------------------------
    # 技能实例化
    # -------------------------------------------------------------------

    def get_instance(self, skill_id: str) -> SkillBase | None:
        """获取技能实例（懒加载）。

        Args:
            skill_id: 技能 ID。

        Returns:
            SkillBase 实例或 None。
        """
        return self._get_or_create_instance(skill_id)

    def _get_or_create_instance(self, skill_id: str) -> SkillBase | None:
        """获取缓存的实例或动态创建新实例。"""
        if skill_id in self._instances:
            return self._instances[skill_id]

        file_mapping = self._file_mappings.get(skill_id)
        if not file_mapping or not self._library_dir:
            return None

        source_path = self._library_dir / file_mapping.file
        if not source_path.exists():
            return None

        try:
            # 动态加载模块
            spec = importlib.util.spec_from_file_location(
                f"skill_library.{skill_id.replace('/', '.')}",
                str(source_path),
            )
            if spec is None or spec.loader is None:
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 获取入口对象
            entry = getattr(module, file_mapping.entry, None)
            if entry is None:
                return None

            # 如果是 SkillBase 子类，实例化并缓存
            if isinstance(entry, type) and issubclass(entry, SkillBase):
                instance = entry()
                self._instances[skill_id] = instance
                return instance

            # 如果已经是实例
            if isinstance(entry, SkillBase):
                self._instances[skill_id] = entry
                return entry

        except Exception:
            pass

        return None

    # -------------------------------------------------------------------
    # 内部方法
    # -------------------------------------------------------------------

    @staticmethod
    def _matches_query(meta: SkillMeta, query: str) -> bool:
        """检查查询关键词是否匹配此技能的 triggers。"""
        query_lower = query.lower()
        return any(t.lower() in query_lower for t in meta.triggers)

    @staticmethod
    def _matches_url(meta: SkillMeta, url: str) -> bool:
        """检查 URL 是否匹配此技能的 url_patterns。

        模式中的 '*' 被视为通配符，其余按子串匹配。
        例如 '*.baidu.com' 匹配 'https://www.baidu.com/path'。
        """
        if not meta.url_patterns:
            return False
        url_lower = url.lower()
        for pattern in meta.url_patterns:
            core = pattern.lower().strip("*")
            if core in url_lower:
                return True
        return False

    def _infer_guide_path(self, file_mapping: SkillFileMapping) -> Path | None:
        """根据技能文件路径推断对应的说明文档路径。"""
        if not self._library_dir:
            return None
        stem = Path(file_mapping.file).stem
        return self._library_dir / "guides" / f"how_to_{stem}.md"


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_instance: SkillRegistry | None = None


def get_skill_registry(library_dir: str | Path | None = None) -> SkillRegistry:
    """获取全局单例 SkillRegistry。

    Args:
        library_dir: 技能库目录路径。若为 None 且单例未初始化，则使用默认路径。
    """
    global _instance
    if _instance is None:
        # 如果没有提供 library_dir，使用默认路径
        if library_dir is None:
            # 默认使用项目根目录下的 src/skill_library
            library_dir = Path(__file__).parent.parent / "skill_library"
        _instance = SkillRegistry(library_dir=library_dir)
        # 自动加载 skills.yaml
        _instance.load_from_yaml()
    return _instance


def reset_skill_registry() -> None:
    """重置全局单例（用于测试）。"""
    global _instance
    _instance = None


# ---------------------------------------------------------------------------
# 向后兼容: SkillEntry 是旧版 API，映射到 SkillMeta
# ---------------------------------------------------------------------------


@dataclass
class SkillEntry:
    """向后兼容的技能条目（旧版 API）。

    新代码应使用 SkillMeta 代替。
    """

    id: str
    name: str
    type: str
    triggers: list[str] = None
    url_patterns: list[str] = None
    file: str = ""
    function: str = ""
    description: str = ""

    def __post_init__(self):
        if self.triggers is None:
            self.triggers = []
        if self.url_patterns is None:
            self.url_patterns = []

    def matches_query(self, query: str) -> bool:
        """检查查询关键词是否匹配此技能。"""
        query_lower = query.lower()
        return any(t.lower() in query_lower for t in self.triggers)

    def matches_url(self, url: str) -> bool:
        """检查 URL 是否匹配此技能的 URL 模式。"""
        if not self.url_patterns:
            return False
        url_lower = url.lower()
        for pattern in self.url_patterns:
            core = pattern.lower().strip("*")
            if core in url_lower:
                return True
        return False
