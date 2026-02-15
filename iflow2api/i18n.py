"""多语言支持模块 (i18n)"""

import json
from pathlib import Path
from typing import Any, Optional

# 当前语言
_current_language: str = "zh"
# 翻译字典缓存
_translations: dict[str, dict[str, Any]] = {}


def get_locales_dir() -> Path:
    """获取语言包目录"""
    return Path(__file__).parent / "locales"


def get_available_languages() -> dict[str, str]:
    """获取可用语言列表
    
    Returns:
        语言代码到语言名称的映射字典，如 {"zh": "简体中文", "en": "English"}
    """
    # 语言代码到显示名称的映射
    language_names = {
        "zh": "简体中文",
        "en": "English",
    }
    
    locales_dir = get_locales_dir()
    if not locales_dir.exists():
        return language_names
    
    languages = {}
    for file in locales_dir.glob("*.json"):
        lang_code = file.stem
        languages[lang_code] = language_names.get(lang_code, lang_code)
    
    return languages if languages else language_names


def load_translation(language: str) -> dict[str, Any]:
    """加载指定语言的翻译文件"""
    locales_dir = get_locales_dir()
    translation_file = locales_dir / f"{language}.json"
    
    if translation_file.exists():
        try:
            with open(translation_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    return {}


def set_language(language: str) -> None:
    """设置当前语言"""
    global _current_language, _translations
    
    if language not in get_available_languages():
        language = "zh"  # 默认中文
    
    _current_language = language
    
    # 加载翻译
    if language not in _translations:
        _translations[language] = load_translation(language)


def get_language() -> str:
    """获取当前语言"""
    return _current_language


def t(key: str, default: Optional[str] = None, **kwargs) -> str:
    """翻译函数
    
    Args:
        key: 翻译键，支持点分隔的嵌套键，如 "app.title"
        default: 默认值，如果翻译不存在则返回此值
        **kwargs: 格式化参数
    
    Returns:
        翻译后的字符串
    """
    # 确保当前语言的翻译已加载
    if _current_language not in _translations:
        _translations[_current_language] = load_translation(_current_language)
    
    translation = _translations.get(_current_language, {})
    
    # 支持嵌套键，如 "app.title"
    keys = key.split(".")
    value = translation
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # 翻译不存在，返回默认值或键本身
            return default if default is not None else key
    
    if not isinstance(value, str):
        return default if default is not None else key
    
    # 格式化字符串
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, ValueError):
            return value
    
    return value


def get_all_translations(language: str) -> dict[str, Any]:
    """获取指定语言的所有翻译"""
    if language not in _translations:
        _translations[language] = load_translation(language)
    return _translations.get(language, {})
