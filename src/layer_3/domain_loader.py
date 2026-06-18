"""Layer 3 - Domain Loader: YAML 配置加载与校验。"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Pydantic 数据模型
# ---------------------------------------------------------------------------


class LocatorItem(BaseModel):
    """单个 UI 元素的定位器集合。CSS 优先级高于 XPath。"""

    css: Optional[List[str]] = None
    xpath: Optional[List[str]] = None


class DomainConfig(BaseModel):
    """站点级别配置，由 YAML 反序列化得到。"""

    name: str
    base_url: Optional[str] = None
    locators: Dict[str, LocatorItem]


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def load_domain(
    domain_name: str,
    domains_dir: str = "domains",
) -> DomainConfig:
    """加载 domains/{domain_name}.yaml 并通过 Pydantic 校验。

    Args:
        domain_name: YAML 文件名（不含扩展名）。
        domains_dir: 存放域配置文件的目录路径。

    Returns:
        校验通过后的配置对象。

    Raises:
        FileNotFoundError: 当 YAML 文件不存在时。
        pydantic.ValidationError: 当 YAML 内容不符合结构时。
    """

    yaml_path = os.path.join(domains_dir, f"{domain_name}.yaml")

    if not os.path.isfile(yaml_path):
        raise FileNotFoundError(f"域配置文件不存在: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    return DomainConfig.model_validate(raw)


def get_element_selectors(
    domain_config: DomainConfig,
    element_name: str,
) -> List[str]:
    """从 DomainConfig 中提取指定元素的所有选择器（CSS 在前，XPath 在后）。

    Args:
        domain_config: 已加载的域配置对象。
        element_name: locators 字典中的键名。

    Returns:
        扁平化的选择器列表：["css1", "css2", "xpath1", "xpath2"]。

    Raises:
        ValueError: 当 element_name 在 locators 中不存在时。
    """

    locator = domain_config.locators.get(element_name)
    if locator is None:
        available = ", ".join(domain_config.locators.keys())
        raise ValueError(
            f"元素 '{element_name}' 不存在于域 '{domain_config.name}' 的 locators 中。"
            f" 可用元素: [{available}]"
        )

    selectors: List[str] = []
    if locator.css:
        selectors.extend(locator.css)
    if locator.xpath:
        selectors.extend(locator.xpath)

    return selectors
