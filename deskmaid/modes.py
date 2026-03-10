"""Classification mode definitions and selection UI."""

from enum import Enum

from rich.console import Console
from rich.prompt import Prompt


class ClassificationMode(Enum):
    QUICK = "quick"
    PERSONAL = "personal"
    DEEP = "deep"


MODE_INFO = {
    ClassificationMode.QUICK: {
        "name": "快速分类",
        "description": "直接扫描并用 AI 分类，保持默认行为",
    },
    ClassificationMode.PERSONAL: {
        "name": "个性化快速分类",
        "description": "先采集你的使用偏好（1-3 轮对话），再进行 AI 分类",
    },
    ClassificationMode.DEEP: {
        "name": "个性化深度分类",
        "description": "采集偏好 + 读取文件内容，辅助 AI 进行更精准的语义分类",
    },
}


def select_mode(console: Console) -> ClassificationMode:
    """Display an interactive menu for the user to choose a classification mode."""
    console.print("\n[bold]请选择分类模式:[/bold]\n")
    modes = list(ClassificationMode)
    for i, mode in enumerate(modes, 1):
        info = MODE_INFO[mode]
        console.print(f"  [bold cyan]{i}[/bold cyan]. {info['name']}  [dim]— {info['description']}[/dim]")

    console.print()
    choice = Prompt.ask("输入编号选择", choices=["1", "2", "3"], default="1")
    return modes[int(choice) - 1]
