# DeskMaid 开发日志

## [0.2.0] - 2026-03-07

### 三模式分类系统

新增三种分类模式，满足不同场景下的整理需求。

#### 新增功能

- **三种分类模式** — 通过交互式菜单或 `--mode` 参数选择：
  - `quick` 快速分类：保持原有行为，直接扫描 + AI 分类
  - `personal` 个性化快速分类：先通过 1-3 轮对话采集用户偏好（职业、文件用途、分类偏好），再结合用户背景进行 AI 分类
  - `deep` 个性化深度分类：在个性化基础上，额外读取文件内容摘要，辅助 AI 进行语义级精准分类
- **用户画像持久化** — 偏好数据保存到 `~/.deskmaid/profile.json`，后续运行可直接复用或更新
- **文件内容提取** — 深度模式支持读取多种格式的文件内容：
  - 纯文本类（.txt, .md, .py, .json 等）
  - Office 文档（.docx, .xlsx, .pptx）
  - PDF 文件（读取前 2 页）
  - 所有读取器均做了异常保护，缺少依赖时自动降级

#### 新增文件

- `deskmaid/modes.py` — 模式枚举定义与交互式选择 UI
- `deskmaid/interview.py` — 用户访谈引擎，含画像加载/保存/对话采集
- `deskmaid/content_reader.py` — 文件内容提取模块，支持文本/Office/PDF

#### 修改文件

- `deskmaid/config.py` — 新增 `PROFILE_FILE` 常量
- `deskmaid/ai_engine.py` — `propose_categories` 和 `classify_items` 新增 `user_context`、`content_data` 参数，扩展 system prompt 支持个性化和内容感知分类
- `deskmaid/cli.py` — `run` 命令新增 `--mode` / `-m` 参数，整合模式选择、用户访谈、内容读取流程
- `pyproject.toml` — 新增依赖：python-docx、openpyxl、python-pptx、pdfplumber

---

## [0.1.0] - 2026-03-06

### 初始版本

首个可用版本，实现了 AI 智能桌面文件整理的核心功能。

#### 功能模块

- **CLI 入口** (`cli.py`) — 基于 Typer + Rich 的命令行界面，支持 `run`、`undo`、`history`、`config` 子命令
- **AI 分类引擎** (`ai_engine.py`) — 两步式分类流程：先提出分类方案，再将文件分配到对应分类
- **文件扫描器** (`scanner.py`) — 桌面文件扫描，自动跳过隐藏文件和 Office 临时文件
- **文件整理器** (`organizer.py`) — 文件移动执行，含冲突处理和事务日志
- **配置管理** (`config.py`) — 支持 Azure OpenAI、OpenAI 及自定义兼容 API 配置
- **撤销机制** (`undo.py`) — 基于事务日志的一键撤销

#### 技术细节

- Python >= 3.10
- 依赖：Typer、Rich、OpenAI Python SDK
- 配置存储路径：`~/.deskmaid/config.json`
- 支持通过 `--path` 指定整理目标路径（默认 `~/Desktop`）
