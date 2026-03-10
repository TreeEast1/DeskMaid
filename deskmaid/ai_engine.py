"""AI classification engine - two-step: propose categories, then classify."""

import json

from openai import AzureOpenAI, OpenAI

from deskmaid.scanner import FileInfo, ScanResult

# Step 1: Propose categories based on actual file contents
PROPOSE_PROMPT = """\
你是一个桌面文件整理助手。用户桌面上有以下文件和文件夹，请根据实际内容提出合理的分类方案。

核心原则:
- 分类应该按照**真实生活场景和用途**来划分，而不是按文件格式（如"文档"、"图片"、"压缩包"）
- 想象一个真实的人如何在桌面上归类自己的东西，例如: Work（工作项目）、Study（学习资料）、Family（家庭生活）、Myself（个人私人）、Tmp（临时待定）
- 同一个场景下的 PDF、PPT、图片、文档应该放在一起，而不是按格式拆开

规则:
1. 分类数量控制在 3-8 个，不要过多也不要过少
2. 类别名称简洁有意义（2-4个字，中英文均可）
3. 已存在的文件夹可以作为分类参考（如果内容相关的话可以复用文件夹名）
4. 每个类别附带简短说明
5. 建议保留一个"临时/待定"类别，用于放置无法明确归类的文件
6. 必须返回严格 JSON

返回格式:
{"categories": [{"name": "类别名", "description": "该类别包含哪些类型的文件"}]}
"""

# Step 2: Classify files AND folders into the proposed categories
CLASSIFY_PROMPT_TEMPLATE = """\
你是一个桌面文件分类助手。请将每个文件和文件夹分类到以下类别之一：

可用类别:
{categories_desc}

规则:
1. 必须返回严格的 JSON 格式
2. 综合考虑名称语义、文件后缀、以及类型（file/folder）
3. 每个项目必须给出分类理由
4. category 字段必须严格匹配上面的类别名
5. 文件夹也要参与分类，整个文件夹会被移入对应类别目录

返回格式:
{{"items": [{{"name": "名称", "type": "file 或 folder", "category": "类别名", "reason": "分类理由"}}]}}
"""


def _make_client(cfg: dict) -> AzureOpenAI | OpenAI:
    provider = cfg.get("provider", "openai")
    if provider == "azure-openai":
        return AzureOpenAI(
            api_key=cfg["api_key"],
            azure_endpoint=cfg["api_base"],
            api_version=cfg.get("api_version", "2024-12-01-preview"),
        )
    return OpenAI(
        api_key=cfg["api_key"],
        base_url=cfg["api_base"],
    )


def _chat(client: AzureOpenAI | OpenAI, model: str, system: str, user: str) -> dict:
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    return json.loads(content)


def propose_categories(
    scan: ScanResult,
    cfg: dict,
    feedback: str = "",
    user_context: str = "",
    content_data: list[dict] | None = None,
) -> list[dict]:
    """Step 1: Let AI propose categories based on file overview, optionally with user feedback."""
    client = _make_client(cfg)
    model = cfg.get("model", "gpt-4o")

    if content_data is not None:
        all_items = content_data
    else:
        all_items = [f.to_dict() for f in scan.files] + [f.to_dict() for f in scan.folders]
    user_msg = f"以下是用户桌面上的所有文件和文件夹:\n{json.dumps(all_items, ensure_ascii=False, indent=2)}"

    if feedback:
        user_msg += f"\n\n用户对分类方案的要求和想法:\n{feedback}"

    system = PROPOSE_PROMPT
    if user_context:
        system += f"\n\n{user_context}\n请结合用户背景信息，提出更贴合其实际使用场景的个性化分类方案。"
    if content_data is not None:
        system += "\n\n部分文件包含 content_preview 字段，这是文件内容摘要。请结合文件内容进行更精准的语义分析和分类。"

    result = _chat(client, model, system, user_msg)
    return result.get("categories", [])


def classify_items(
    items: list[FileInfo],
    categories: list[dict],
    cfg: dict,
    user_context: str = "",
    content_data: list[dict] | None = None,
) -> list[dict]:
    """Step 2: Classify each file and folder into the confirmed categories."""
    client = _make_client(cfg)
    model = cfg.get("model", "gpt-4o")

    categories_desc = "\n".join(
        f"- {cat['name']}: {cat.get('description', '')}" for cat in categories
    )
    system = CLASSIFY_PROMPT_TEMPLATE.format(categories_desc=categories_desc)

    if user_context:
        system += f"\n\n{user_context}\n请结合用户背景信息进行分类。"
    if content_data is not None:
        system += "\n\n部分文件包含 content_preview 字段，请结合 content_preview 字段的文件内容摘要进行语义分类。"

    if content_data is not None:
        item_list = content_data
    else:
        item_list = [f.to_dict() for f in items]
    user_msg = f"请对以下文件和文件夹进行分类:\n{json.dumps(item_list, ensure_ascii=False, indent=2)}"

    result = _chat(client, model, system, user_msg)
    classified = result.get("items", [])

    # Validate categories
    valid = {cat["name"] for cat in categories}
    for item in classified:
        if item.get("category") not in valid:
            item["category"] = categories[0]["name"] if categories else "其他"

    return classified
