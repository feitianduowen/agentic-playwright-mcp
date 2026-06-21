"""
脚本持久化存储 —— 保存、加载、管理 AI 生成的脚本。

脚本存储在 scripts/ 目录下，按任务描述的哈希命名。
支持元数据记录（创建时间、执行次数、成功率等）。
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class ScriptRecord:
    """脚本记录。"""

    id: str  # 基于任务描述的哈希
    task: str  # 原始任务描述
    script: str  # 脚本内容
    created_at: float = 0.0  # 创建时间戳
    last_used_at: float = 0.0  # 最后使用时间
    use_count: int = 0  # 使用次数
    success_count: int = 0  # 成功次数
    tags: list[str] = field(default_factory=list)  # 标签

    @property
    def success_rate(self) -> float:
        """成功率。"""
        if self.use_count == 0:
            return 0.0
        return self.success_count / self.use_count

    def to_dict(self) -> dict:
        """转换为字典。"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ScriptRecord:
        """从字典创建。"""
        return cls(**data)


class ScriptStore:
    """脚本持久化存储。"""

    def __init__(self, store_dir: str | Path | None = None) -> None:
        """初始化存储。

        Args:
            store_dir: 存储目录，默认为项目根目录下的 scripts/。
        """
        if store_dir is None:
            project_root = Path(__file__).resolve().parent.parent.parent
            store_dir = project_root / "scripts"

        self._store_dir = Path(store_dir)
        self._store_dir.mkdir(parents=True, exist_ok=True)

        # 索引文件
        self._index_path = self._store_dir / "index.json"
        self._index: dict[str, ScriptRecord] = {}
        self._load_index()

    def save(self, task: str, script: str, tags: list[str] | None = None) -> ScriptRecord:
        """保存脚本。

        Args:
            task: 任务描述。
            script: 脚本内容。
            tags: 可选标签。

        Returns:
            ScriptRecord。
        """
        script_id = self._generate_id(task)

        # 如果已存在，更新
        if script_id in self._index:
            record = self._index[script_id]
            record.script = script
            record.last_used_at = time.time()
            if tags:
                record.tags = list(set(record.tags + tags))
        else:
            record = ScriptRecord(
                id=script_id,
                task=task,
                script=script,
                created_at=time.time(),
                last_used_at=time.time(),
                tags=tags or [],
            )
            self._index[script_id] = record

        # 保存脚本文件
        script_path = self._store_dir / f"{script_id}.py"
        script_path.write_text(script, encoding="utf-8")

        # 更新索引
        self._save_index()

        return record

    def load(self, script_id: str) -> ScriptRecord | None:
        """加载脚本。

        Args:
            script_id: 脚本 ID。

        Returns:
            ScriptRecord 或 None。
        """
        return self._index.get(script_id)

    def search(self, query: str) -> list[ScriptRecord]:
        """搜索脚本。

        Args:
            query: 搜索关键词。

        Returns:
            匹配的脚本列表。
        """
        query_lower = query.lower()
        results = []
        for record in self._index.values():
            if query_lower in record.task.lower():
                results.append(record)
        return results

    def list_all(self) -> list[ScriptRecord]:
        """列出所有脚本。"""
        return list(self._index.values())

    def delete(self, script_id: str) -> bool:
        """删除脚本。

        Args:
            script_id: 脚本 ID。

        Returns:
            是否成功删除。
        """
        if script_id not in self._index:
            return False

        # 删除文件
        script_path = self._store_dir / f"{script_id}.py"
        if script_path.exists():
            script_path.unlink()

        # 从索引中删除
        del self._index[script_id]
        self._save_index()

        return True

    def record_usage(self, script_id: str, success: bool) -> None:
        """记录脚本使用情况。

        Args:
            script_id: 脚本 ID。
            success: 是否成功。
        """
        record = self._index.get(script_id)
        if record:
            record.use_count += 1
            record.last_used_at = time.time()
            if success:
                record.success_count += 1
            self._save_index()

    def find_by_task(self, task: str) -> ScriptRecord | None:
        """精确查找脚本（基于任务描述哈希）。"""
        script_id = self._generate_id(task)
        return self._index.get(script_id)

    def _generate_id(self, task: str) -> str:
        """根据任务描述生成唯一 ID。"""
        return hashlib.md5(task.encode("utf-8")).hexdigest()[:12]

    def _load_index(self) -> None:
        """加载索引文件。"""
        if not self._index_path.exists():
            return

        try:
            with open(self._index_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("scripts", []):
                record = ScriptRecord.from_dict(item)
                self._index[record.id] = record
        except (json.JSONDecodeError, KeyError):
            pass

    def _save_index(self) -> None:
        """保存索引文件。"""
        data = {
            "scripts": [record.to_dict() for record in self._index.values()],
            "updated_at": time.time(),
        }
        with open(self._index_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# 全局单例
# ---------------------------------------------------------------------------

_instance: ScriptStore | None = None


def get_script_store(store_dir: str | Path | None = None) -> ScriptStore:
    """获取全局单例 ScriptStore。"""
    global _instance
    if _instance is None:
        _instance = ScriptStore(store_dir=store_dir)
    return _instance


def reset_script_store() -> None:
    """重置全局单例（用于测试）。"""
    global _instance
    _instance = None
