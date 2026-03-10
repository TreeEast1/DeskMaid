"""User interview engine - collects preferences for personalized classification."""

import json
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from deskmaid.config import PROFILE_FILE, ensure_dirs


def load_profile() -> dict:
    """Load existing user profile from disk."""
    if PROFILE_FILE.exists():
        return json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
    return {}


def save_profile(profile: dict) -> None:
    """Save user profile to disk."""
    ensure_dirs()
    PROFILE_FILE.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def conduct_interview(
    console: Console,
    existing_profile: dict | None = None,
    *,
    demo: bool = False,
) -> dict:
    """Conduct a 1-3 round interview to collect user preferences.

    If an existing profile is found, let the user choose to reuse, update, or redo it.
    """
    if demo:
        # Minimal, deterministic profile for demo/screenshot runs
        return {
            "role": "学生/开发者",
            "file_patterns": "课程笔记、论文PDF、PPT/报告、项目资料、截图与临时下载",
            "preferences": "优先按 工作/学习/生活/杂项 分类；工作中再按项目归类",
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    if existing_profile:
        console.print(Panel(
            f"职业/角色: [bold]{existing_profile.get('role', '未设置')}[/bold]\n"
            f"文件类型和用途: [bold]{existing_profile.get('file_patterns', '未设置')}[/bold]\n"
            f"分类偏好: [bold]{existing_profile.get('preferences', '未设置')}[/bold]\n"
            f"更新时间: [dim]{existing_profile.get('updated_at', '未知')}[/dim]",
            title="已有用户画像",
            border_style="blue",
        ))
        action = Prompt.ask(
            "选择操作",
            choices=["使用", "更新", "重新填写"],
            default="使用",
        )
        if action == "使用":
            return existing_profile
        if action == "更新":
            # Pre-fill with existing values, user can just press Enter to keep
            return _do_interview(console, defaults=existing_profile)
        # "重新填写" falls through to fresh interview

    return _do_interview(console)


def _do_interview(console: Console, defaults: dict | None = None) -> dict:
    """Run the actual interview rounds."""
    defaults = defaults or {}

    console.print(Panel(
        "[bold]第 1 轮：了解你的身份[/bold]",
        border_style="green",
    ))
    role_default = defaults.get("role") or None
    role = Prompt.ask(
        "你的职业或角色是什么？（如：学生、设计师、程序员、产品经理等）",
        default=role_default,
    )

    console.print(Panel(
        "[bold]第 2 轮：了解你的文件[/bold]",
        border_style="green",
    ))
    fp_default = defaults.get("file_patterns") or None
    file_patterns = Prompt.ask(
        "你桌面上通常有哪些类型的文件？主要用途是什么？\n"
        "（如：工作文档和PPT、课程作业、设计稿、代码项目、截图等）",
        default=fp_default,
    )

    console.print(Panel(
        "[bold]第 3 轮：分类偏好（可跳过）[/bold]",
        border_style="green",
    ))
    if Confirm.ask("是否想指定你偏好的分类方式？", default=False):
        pref_default = defaults.get("preferences") or None
        preferences = Prompt.ask(
            "请描述你喜欢的分类方式\n"
            "（如：按项目分类、按工作/生活分、按紧急程度分等）",
            default=pref_default,
        )
    else:
        preferences = defaults.get("preferences", "")

    return {
        "role": role,
        "file_patterns": file_patterns,
        "preferences": preferences,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def profile_to_prompt_context(profile: dict) -> str:
    """Convert a user profile dict into natural language context for AI prompts."""
    parts = []
    if profile.get("role"):
        parts.append(f"用户是一名{profile['role']}")
    if profile.get("file_patterns"):
        parts.append(f"桌面上通常有：{profile['file_patterns']}")
    if profile.get("preferences"):
        parts.append(f"用户偏好的分类方式：{profile['preferences']}")

    if not parts:
        return ""
    return "用户背景信息：\n" + "。\n".join(parts) + "。\n请结合以上用户背景，提出更贴合用户实际使用场景的分类方案。"
