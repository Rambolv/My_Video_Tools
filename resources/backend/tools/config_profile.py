# -*- coding: utf-8 -*-
"""
@desc: 配置方案管理 — 导出/导入全部软件设置到 JSON 配置文件
"""
import json, os
from datetime import datetime
from typing import Dict, Any

from backend.config import config, VERSION
from qfluentwidgets import ConfigItem, OptionsConfigItem, RangeConfigItem


# 导出/导入时排除的配置属性名（UI布局/窗口位置等）
_EXCLUDED_ATTRS = {
    "windowX", "windowY", "windowW", "windowH",
    "removalCardCollapsed", "extractCardCollapsed",
    "watermarkSectionCollapsed", "skipStartupDialog",
    "startupDonateCount", "saveDirectory",
    "watermarkTemplatePath", "fiModelDir",
    "checkUpdateOnStartup", "interface",
    "intefaceTexts",
}


def _iter_items():
    """遍历 Config 类的所有 ConfigItem 属性，返回 (attr_name, item)"""
    for attr_name in dir(config):
        if attr_name.startswith("_"):
            continue
        attr = getattr(config, attr_name, None)
        if isinstance(attr, (ConfigItem, OptionsConfigItem, RangeConfigItem)):
            yield attr_name, attr


def _get_value(item) -> Any:
    """获取 ConfigItem 的可序列化值"""
    v = item.value
    if hasattr(v, "value"):   # 枚举 → 字符串
        return v.value
    return v


def _set_value(item, val: Any):
    """设置 ConfigItem 的值（处理枚举类型）"""
    from qfluentwidgets import OptionsConfigItem
    if isinstance(item, OptionsConfigItem) and hasattr(item, "validator"):
        opts = item.validator.options
        if opts and hasattr(opts[0], "value"):
            # 枚举选项
            for opt in opts:
                if opt.value == val:
                    config.set(item, opt)
                    return
        elif val in opts:
            config.set(item, val)
            return
    # 普通值类型
    config.set(item, val)


def export_config() -> Dict[str, Any]:
    """导出全部配置（排除UI布局项）"""
    data = {}
    for name, item in _iter_items():
        if name in _EXCLUDED_ATTRS:
            continue
        try:
            val = _get_value(item)
            # 确保值可 JSON 序列化
            json.dumps(val)
            data[name] = val
        except (TypeError, ValueError):
            print(f"[ConfigProfile] 跳过不可序列化的配置项: {name} ({type(val).__name__})")
        except Exception:
            pass
    return data


def export_config_to_json(filepath: str) -> bool:
    """导出配置到 JSON 文件"""
    try:
        data = export_config()
        payload = {
            "_meta": {
                "export_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "version": VERSION,
                "description": "VSR 魔改版 配置方案",
            },
            "config": data,
        }
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ConfigProfile] 导出失败: {e}")
        return False


def import_config_from_dict(data: Dict[str, Any]) -> int:
    """从字典导入配置"""
    count = 0
    for name, item in _iter_items():
        if name not in data:
            continue
        try:
            _set_value(item, data[name])
            count += 1
        except Exception as e:
            print(f"[ConfigProfile] 跳过 {name}: {e}")
    return count


def import_config_from_json(filepath: str) -> int:
    """从 JSON 文件导入配置"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            payload = json.load(f)
        data = payload.get("config", payload)
        return import_config_from_dict(data)
    except Exception as e:
        print(f"[ConfigProfile] 导入失败: {e}")
        return 0
