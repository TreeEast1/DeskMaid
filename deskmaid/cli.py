"""DeskMaid CLI - AI-powered desktop file organizer."""

import json
from collections import Counter
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from deskmaid.ai_engine import classify_items, propose_categories
from deskmaid.config import (
    PROVIDER_TEMPLATES,
    get_desktop_path,
    load_config,
    save_config,
)
from deskmaid.content_reader import enrich_items_with_content
from deskmaid.interview import (
    conduct_interview,
    load_profile,
    profile_to_prompt_context,
    save_profile,
)
from deskmaid.modes import ClassificationMode, MODE_INFO, select_mode
from deskmaid.organizer import organize
from deskmaid.scanner import scan_desktop
from deskmaid.undo import get_history_logs, get_last_log, undo_last

app = typer.Typer(help="DeskMaid - AI 智能桌面整理工具")
console = Console()

BANNER = Panel(
    "[bold cyan]DeskMaid[/bold cyan]  [dim]— AI 智能桌面整理工具[/dim]",
    style="cyan",
    expand=False,
)


@app.command()
def run(
    path: Optional[str] = typer.Option(None, "--path", "-p", help="目标路径（默认 ~/Desktop）"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="分类模式: quick/personal/deep"),
) -> None:
    """扫描桌面文件，AI 分类，展示预案并执行整理。"""
    console.print(BANNER)

    cfg = load_config()
    if not cfg.get("api_key"):
        console.print(Panel(
            "[bold red]请先运行 deskmaid config 配置 API[/bold red]",
            title="⚠ 配置缺失",
            border_style="red",
        ))
        raise typer.Exit(1)

    desktop = Path(path) if path else get_desktop_path(cfg)
    if not desktop.exists():
        console.print(Panel(
            f"[red]路径不存在: {desktop}[/red]\n[dim]请检查路径是否正确，或使用 --path 指定其他目录[/dim]",
            title="⚠ 错误",
            border_style="red",
        ))
        raise typer.Exit(1)

    # Step 0: Scan with spinner
    with console.status("[bold green]正在扫描目录...[/bold green]"):
        scan = scan_desktop(desktop)
    all_items = scan.files + scan.folders
    if not all_items:
        console.print(Panel(
            "[yellow]没有找到需要整理的文件。[/yellow]",
            title="扫描完成",
            border_style="yellow",
        ))
        raise typer.Exit(0)

    console.print(Panel(
        f"📂 目录: [bold]{desktop}[/bold]\n"
        f"📄 文件: [bold]{len(scan.files)}[/bold] 个    "
        f"📁 文件夹: [bold]{len(scan.folders)}[/bold] 个",
        title="扫描结果",
        border_style="green",
    ))

    # Mode selection
    if mode:
        valid_modes = {m.value for m in ClassificationMode}
        if mode not in valid_modes:
            console.print(Panel(
                f"[red]无效的模式: {mode}[/red]\n[dim]可用模式: {', '.join(valid_modes)}[/dim]",
                title="⚠ 错误",
                border_style="red",
            ))
            raise typer.Exit(1)
        selected_mode = ClassificationMode(mode)
    else:
        selected_mode = select_mode(console)

    mode_info = MODE_INFO[selected_mode]
    console.print(Panel(
        f"[bold]{mode_info['name']}[/bold]  [dim]— {mode_info['description']}[/dim]",
        title="当前模式",
        border_style="magenta",
    ))

    # Personalization: interview + profile
    user_context = ""
    content_data = None

    if selected_mode in (ClassificationMode.PERSONAL, ClassificationMode.DEEP):
        existing_profile = load_profile()
        profile = conduct_interview(console, existing_profile or None)
        save_profile(profile)
        user_context = profile_to_prompt_context(profile)

    # Deep mode: read file contents
    if selected_mode == ClassificationMode.DEEP:
        with console.status("[bold green]正在读取文件内容...[/bold green]"):
            content_data = enrich_items_with_content(all_items)

    # Step 1: AI proposes categories (with feedback loop)
    feedback = ""
    while True:
        with console.status("[bold green]AI 正在分析文件，生成分类方案...[/bold green]"):
            try:
                categories = propose_categories(
                    scan, cfg, feedback=feedback,
                    user_context=user_context, content_data=content_data,
                )
            except Exception as e:
                console.print(Panel(
                    f"[red]AI 分类方案生成失败: {e}[/red]\n[dim]请检查 API 配置和网络连接[/dim]",
                    title="⚠ 错误",
                    border_style="red",
                ))
                raise typer.Exit(1)

        if not categories:
            console.print(Panel(
                "[yellow]AI 未返回分类方案。[/yellow]",
                title="⚠ 提示",
                border_style="yellow",
            ))
            raise typer.Exit(1)

        # Display proposed categories
        cat_table = Table(show_lines=True)
        cat_table.add_column("#", style="dim", justify="center", width=3)
        cat_table.add_column("类别", style="bold cyan")
        cat_table.add_column("说明", style="dim")

        for i, cat in enumerate(categories, 1):
            cat_table.add_row(str(i), cat["name"], cat.get("description", ""))

        console.print(Panel(cat_table, title="AI 建议的分类方案", border_style="blue"))

        if Confirm.ask("\n接受此分类方案？"):
            break

        # User provides free-form feedback for next round
        feedback = Prompt.ask("\n请输入你的想法（如：想按项目分、合并某些类、增加XX类别等）")
        if not feedback.strip():
            console.print(Panel(
                "[yellow]操作已取消。[/yellow]",
                title="取消",
                border_style="yellow",
            ))
            raise typer.Exit(0)

    # Step 2: AI classifies files and folders into confirmed categories
    with console.status("[bold green]AI 正在将文件和文件夹分配到各分类...[/bold green]"):
        try:
            plan = classify_items(
                all_items, categories, cfg,
                user_context=user_context, content_data=content_data,
            )
        except Exception as e:
            console.print(Panel(
                f"[red]AI 分类失败: {e}[/red]\n[dim]请检查 API 配置和网络连接[/dim]",
                title="⚠ 错误",
                border_style="red",
            ))
            raise typer.Exit(1)

    if not plan:
        console.print(Panel(
            "[yellow]AI 未返回分类结果。[/yellow]",
            title="⚠ 提示",
            border_style="yellow",
        ))
        raise typer.Exit(1)

    # Display classification plan
    plan_table = Table(show_lines=True, expand=True)
    plan_table.add_column("名称", style="cyan", overflow="ellipsis", no_wrap=True)
    plan_table.add_column("类型", justify="center", width=4)
    plan_table.add_column("分类", style="green", no_wrap=True, min_width=8)

    category_counter: Counter[str] = Counter()
    for item in plan:
        type_icon = "📁" if item.get("type") == "folder" else "📄"
        plan_table.add_row(item["name"], type_icon, item["category"])
        category_counter[item["category"]] += 1

    console.print(Panel(plan_table, title="整理预案", border_style="blue"))

    # Summary under the plan table
    summary_parts = [f"[bold]{cat}[/bold]: {count}" for cat, count in category_counter.most_common()]
    console.print(f"  [dim]分类统计:[/dim] {' | '.join(summary_parts)}\n")

    # Confirm execution
    if not Confirm.ask("确认执行整理？"):
        console.print(Panel(
            "[yellow]操作已取消。[/yellow]",
            title="取消",
            border_style="yellow",
        ))
        raise typer.Exit(0)

    # Execute with progress bar
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("整理中...", total=len(plan))

        def on_progress(filename: str, index: int, total: int) -> None:
            progress.update(task, completed=index, description=f"移动: {filename}")

        log = organize(desktop, plan, on_progress=on_progress)

    moved = len(log["moves"])

    # Completion summary panel
    move_counter: Counter[str] = Counter()
    for m in log["moves"]:
        move_counter[m.get("category", "未知")] += 1

    summary_lines = [f"[bold green]已移动 {moved} 个文件/文件夹[/bold green]\n"]
    for cat, count in move_counter.most_common():
        summary_lines.append(f"  📂 [bold]{cat}[/bold]: {count} 个")
    summary_lines.append(f"\n[dim]如需撤销，运行: deskmaid undo[/dim]")

    console.print(Panel(
        "\n".join(summary_lines),
        title="✅ 整理完成",
        border_style="green",
    ))


@app.command()
def undo() -> None:
    """撤销上一次整理操作。"""
    last_log = get_last_log()
    if last_log is None:
        console.print(Panel(
            "[yellow]没有可撤销的操作。[/yellow]",
            title="撤销",
            border_style="yellow",
        ))
        raise typer.Exit(0)

    moves = last_log.get("moves", [])
    ts = last_log.get("timestamp", "未知")

    # Show what will be restored
    undo_table = Table(show_lines=True)
    undo_table.add_column("#", style="dim", justify="center", width=4)
    undo_table.add_column("文件名", style="cyan")
    undo_table.add_column("当前位置", style="red")
    undo_table.add_column("→ 恢复到", style="green")

    for i, m in enumerate(moves, 1):
        undo_table.add_row(
            str(i),
            m["filename"],
            str(Path(m["dst"]).parent),
            str(Path(m["src"]).parent),
        )

    console.print(Panel(
        undo_table,
        title=f"将要撤销的操作 ({ts})",
        border_style="yellow",
    ))

    if not Confirm.ask(f"\n确认撤销？将恢复 {len(moves)} 个文件"):
        console.print(Panel(
            "[yellow]操作已取消。[/yellow]",
            title="取消",
            border_style="yellow",
        ))
        raise typer.Exit(0)

    log = undo_last()
    if log is None:
        console.print(Panel(
            "[red]撤销失败，日志文件可能已被删除。[/red]",
            title="⚠ 错误",
            border_style="red",
        ))
        raise typer.Exit(1)

    moved = len(log.get("moves", []))
    console.print(Panel(
        f"[bold green]已撤销！{moved} 个文件已恢复原位。[/bold green]",
        title="✅ 撤销完成",
        border_style="green",
    ))


@app.command()
def config() -> None:
    """交互式配置 API 连接。"""
    console.print(BANNER)
    cfg = load_config()

    # --- API Provider ---
    console.print(Panel("[bold]API 提供商配置[/bold]", title="1/3 提供商", style="blue"))

    provider = Prompt.ask(
        "选择 API 提供商",
        choices=["azure-openai", "openai", "custom"],
        default=cfg.get("provider", "azure-openai"),
    )
    template = PROVIDER_TEMPLATES[provider]

    # --- Connection ---
    console.print(Panel("[bold]连接参数配置[/bold]", title="2/3 连接", style="blue"))

    api_base = Prompt.ask("API Base URL", default=cfg.get("api_base", template["api_base"]))
    api_key = Prompt.ask("API Key", password=True, default=cfg.get("api_key", ""))
    model = Prompt.ask("模型名称", default=cfg.get("model", template["model"]))

    api_version = ""
    if provider == "azure-openai":
        api_version = Prompt.ask("API Version", default=cfg.get("api_version", template["api_version"]))

    # --- Paths ---
    console.print(Panel("[bold]路径配置[/bold]", title="3/3 路径", style="blue"))

    desktop_path = Prompt.ask("桌面路径", default=cfg.get("desktop_path", str(Path.home() / "Desktop")))

    new_cfg = {
        "provider": provider,
        "api_base": api_base,
        "api_key": api_key,
        "model": model,
        "api_version": api_version,
        "desktop_path": desktop_path,
    }
    save_config(new_cfg)

    # Config summary with masked API key
    masked_key = api_key[:4] + "****" + api_key[-4:] if len(api_key) > 8 else "****"
    summary = (
        f"提供商: [bold]{provider}[/bold]\n"
        f"API Base: [bold]{api_base}[/bold]\n"
        f"API Key: [dim]{masked_key}[/dim]\n"
        f"模型: [bold]{model}[/bold]\n"
    )
    if api_version:
        summary += f"API Version: [bold]{api_version}[/bold]\n"
    summary += f"桌面路径: [bold]{desktop_path}[/bold]"

    console.print(Panel(
        summary,
        title="✅ 配置已保存",
        border_style="green",
    ))


@app.command()
def history() -> None:
    """查看历史操作记录。"""
    logs = get_history_logs()
    if not logs:
        console.print(Panel(
            "[yellow]暂无历史记录。[/yellow]",
            title="历史记录",
            border_style="yellow",
        ))
        raise typer.Exit(0)

    table = Table(title="操作历史", show_lines=True)
    table.add_column("#", style="dim", justify="center", width=4)
    table.add_column("时间", style="cyan")
    table.add_column("文件数", justify="center")
    table.add_column("分类", style="green")
    table.add_column("详情", style="dim")

    for idx, log_file in enumerate(logs[:10], 1):
        log = json.loads(log_file.read_text(encoding="utf-8"))
        ts = log.get("timestamp", "?")
        moves = log.get("moves", [])

        # Collect categories
        cats = Counter(m.get("category", "?") for m in moves)
        cat_str = ", ".join(f"{c}({n})" for c, n in cats.most_common())

        details = ", ".join(m["filename"] for m in moves[:3])
        if len(moves) > 3:
            details += f" ... (+{len(moves) - 3})"
        table.add_row(str(idx), ts, str(len(moves)), cat_str, details)

    console.print(table)


if __name__ == "__main__":
    app()
