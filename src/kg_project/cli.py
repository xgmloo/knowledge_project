from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import Settings, ensure_dirs
from .extractor import OllamaExtractor
from .models import Chunk, ExtractionResult
from .neo4j_store import Neo4jStore
from .parser import PDFParser
from .visualize import render_subgraph

app = typer.Typer(help="教材知识图谱构建工具")
console = Console()


def _load_chunks(path: Path) -> list[Chunk]:
    chunks = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            chunks.append(Chunk(**json.loads(line)))
    return chunks


@app.command()
def parse(
    pdf_dir: Path = typer.Option(Path("data/pdfs"), help="教材 PDF 文件夹"),
    out_file: Path = typer.Option(Path("data/outputs/chunks.jsonl"), help="chunk 输出路径"),
) -> None:
    settings = Settings(pdf_dir=pdf_dir, chunks_file=out_file)
    ensure_dirs(settings)

    parser = PDFParser(settings.images_dir)
    chunks = parser.parse_folder(settings.pdf_dir)
    parser.dump_jsonl(chunks, settings.chunks_file)
    console.print(f"[green]完成解析: {len(chunks)} chunks -> {settings.chunks_file}")


@app.command()
def extract(
    chunks_file: Path = typer.Option(Path("data/outputs/chunks.jsonl"), help="chunk 文件"),
    out_file: Path = typer.Option(Path("data/outputs/extractions.jsonl"), help="抽取结果"),
    max_chunks: int = typer.Option(0, help="仅处理前 N 个 chunk，0 表示全部"),
) -> None:
    settings = Settings(chunks_file=chunks_file, extraction_file=out_file)
    ensure_dirs(settings)

    extractor = OllamaExtractor(settings.ollama_base_url, settings.ollama_model)
    chunks = _load_chunks(settings.chunks_file)
    if max_chunks > 0:
        chunks = chunks[:max_chunks]

    with settings.extraction_file.open("w", encoding="utf-8") as f:
        for c in chunks:
            result = extractor.extract(c.chunk_id, c.text, c.images, c.formula_candidates)
            f.write(json.dumps(result.model_dump(), ensure_ascii=False) + "\n")
    console.print(f"[green]完成抽取: {len(chunks)} chunks -> {settings.extraction_file}")


@app.command()
def ingest(
    extraction_file: Path = typer.Option(Path("data/outputs/extractions.jsonl"), help="抽取结果文件"),
) -> None:
    settings = Settings(extraction_file=extraction_file)
    store = Neo4jStore(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    store.init_constraints()

    entity_count = 0
    relation_count = 0
    with settings.extraction_file.open("r", encoding="utf-8") as f:
        for line in f:
            item = ExtractionResult(**json.loads(line))
            store.upsert_entities(item.entities)
            store.upsert_relations(item.relations)
            entity_count += len(item.entities)
            relation_count += len(item.relations)

    stats = store.graph_stats()
    store.close()

    table = Table(title="导入完成")
    table.add_column("指标")
    table.add_column("数量", justify="right")
    table.add_row("本次写入实体", str(entity_count))
    table.add_row("本次写入关系", str(relation_count))
    table.add_row("图谱实体总数", str(stats["entity_count"]))
    table.add_row("图谱关系总数", str(stats["relation_count"]))
    console.print(table)


@app.command()
def subgraph(
    keyword: str = typer.Option(..., help="关键词"),
    out_html: Path = typer.Option(Path("data/outputs/subgraph.html"), help="可视化输出 HTML"),
    limit: int = typer.Option(100, help="子图最大记录数"),
) -> None:
    settings = Settings()
    store = Neo4jStore(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password)
    sg = store.subgraph_by_keyword(keyword, limit)
    store.close()

    render_path = render_subgraph(sg, out_html)
    console.print(f"[green]子图可视化输出: {render_path}")


@app.command()
def run_all(
    pdf_dir: Path = typer.Option(Path("data/pdfs"), help="PDF 文件夹"),
    max_chunks: int = typer.Option(0, help="抽取前 N 个 chunk (0=全部)"),
) -> None:
    parse(pdf_dir=pdf_dir)
    extract(max_chunks=max_chunks)
    ingest()
    console.print("[green]全流程完成，可运行 subgraph 命令进行可视化。")


if __name__ == "__main__":
    app()
