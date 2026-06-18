"""Layer 3 - Config Updater: 自愈写入 YAML。"""

from __future__ import annotations

import os
from typing import List

import yaml


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _is_xpath(selector: str) -> bool:
    """判断选择器是否为 XPath 表达式。XPath 以 / 或 // 开头。"""
    stripped = selector.strip()
    return stripped.startswith("/") or stripped.startswith("//")


# ---------------------------------------------------------------------------
# 公开 API
# ---------------------------------------------------------------------------


def update_selector_priority(
    domain_name: str,
    element_name: str,
    successful_selector: str,
    domains_dir: str = "domains",
) -> bool:
    """将成功的选择器提升到对应列表的第一位（自愈机制）。

    Args:
        domain_name: YAML 文件名（不含扩展名）。
        element_name: locators 字典中的键名。
        successful_selector: 本次成功使用的选择器字符串。
        domains_dir: 存放域配置文件的目录路径。

    Returns:
        True 表示成功更新并写回文件；False 表示无需更新或出错。
    """

    yaml_path = os.path.join(domains_dir, f"{domain_name}.yaml")

    if not os.path.isfile(yaml_path):
        return False

    # ---- 读取 ----
    with open(yaml_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    if data is None:
        return False

    locators = data.get("locators", {})
    element_locators = locators.get(element_name)

    if element_locators is None:
        return False

    # ---- 判断属于 css 还是 xpath ----
    is_xpath = _is_xpath(successful_selector)
    key = "xpath" if is_xpath else "css"
    selector_list: List[str] = element_locators.get(key, [])

    if successful_selector not in selector_list:
        return False

    # ---- 已经在第一位则无需改动 ----
    if selector_list[0] == successful_selector:
        return True

    # ---- 移到第一位 ----
    selector_list.remove(successful_selector)
    selector_list.insert(0, successful_selector)
    element_locators[key] = selector_list
    locators[element_name] = element_locators
    data["locators"] = locators

    # ---- 写回 ----
    with open(yaml_path, "w", encoding="utf-8") as fh:
        yaml.dump(
            data,
            fh,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )

    return True
