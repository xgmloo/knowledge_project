# knowledge_project

教材知识图谱构建项目（Python + Ollama + Neo4j）。

## 功能概览

- **教材解析模块**
  - 批量读取 `data/pdfs/` 下多个 PDF。
  - 抽取页内文本。
  - 提取页内图片并保存为 PNG。
  - 识别公式候选（基于符号与正则的启发式规则）。
  - 按 chunk 切分，输出结构化 JSONL。
- **多模态抽取模块**
  - 将文本 + 图片 + 公式候选调用 Ollama `/api/generate`。
  - 默认模型：`qwen3-vl:30b`。
  - 按 JSON 约束解析为实体/关系。
- **Neo4j 写入与查询模块**
  - 创建实体唯一约束。
  - 实体与关系 upsert。
  - 图谱统计（实体数/关系数）。
  - 根据关键词抽取子图。
- **可视化模块**
  - 将子图导出为交互式 HTML（PyVis）。

---

## 项目结构

```text
knowledge_project/
├── data/
│   ├── pdfs/                  # 放置教材 PDF（多个文件）
│   └── outputs/
│       ├── images/            # 提取图片输出目录
│       ├── chunks.jsonl       # 解析输出
│       ├── extractions.jsonl  # 抽取输出
│       └── subgraph.html      # 可视化输出
├── src/kg_project/
│   ├── cli.py                 # 命令行入口
│   ├── config.py              # 配置
│   ├── parser.py              # PDF解析
│   ├── extractor.py           # Ollama多模态抽取
│   ├── neo4j_store.py         # Neo4j写入/查询
│   ├── visualize.py           # 子图可视化
│   └── models.py              # 数据模型
├── environment.yml            # Conda环境
└── pyproject.toml
```

---

## 1) Conda 环境

```bash
conda env create -f environment.yml
conda activate kg_project
pip install -e .
```

---

## 2) 服务配置

可通过环境变量覆盖默认值：

```bash
export OLLAMA_BASE_URL=http://<your-server-ip>:11500
export OLLAMA_MODEL=qwen3-vl:30b

export NEO4J_URI=bolt://<your-server-ip>:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=password123
```

> 如果在同一台远程服务器执行，也可以使用默认值（127.0.0.1）。

---

## 3) 准备教材 PDF

将教材 PDF 文件放入：

```text
data/pdfs/
```

支持多个 PDF 批处理。

---

## 4) 运行流程

### 4.1 仅解析

```bash
kg-project parse --pdf-dir data/pdfs --out-file data/outputs/chunks.jsonl
```

### 4.2 调用 Ollama 进行多模态抽取

```bash
kg-project extract \
  --chunks-file data/outputs/chunks.jsonl \
  --out-file data/outputs/extractions.jsonl
```

> 调试建议：可加 `--max-chunks 5` 先小规模验证。

### 4.3 导入 Neo4j

```bash
kg-project ingest --extraction-file data/outputs/extractions.jsonl
```

### 4.4 按关键词导出子图可视化

```bash
kg-project subgraph --keyword "牛顿第二定律" --out-html data/outputs/subgraph.html
```

打开 `data/outputs/subgraph.html` 即可交互浏览。

### 4.5 一键全流程

```bash
kg-project run-all --pdf-dir data/pdfs --max-chunks 0
```

---

## 输出数据格式（简化）

### chunks.jsonl

```json
{"chunk_id":"book1-p1-c1","pdf_file":"book1.pdf","page":1,"text":"...","images":["...png"],"formula_candidates":["F=ma"]}
```

### extractions.jsonl

```json
{"chunk_id":"book1-p1-c1","entities":[{"name":"牛顿第二定律","type":"Formula"}],"relations":[{"source":"牛顿第二定律","target":"力","type":"相关于"}]}
```

---

## 说明

- 公式候选识别是启发式，适合作为 LLM 抽取前的提示增强。
- 关系在 Neo4j 中统一存为 `:RELATED`，关系语义保存在 `r.type` 字段。
- 若需增强精度，可对不同学科设计专用 prompt 与后处理规则。
