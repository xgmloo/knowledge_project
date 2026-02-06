from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Entity(BaseModel):
    name: str
    type: str = "Concept"
    description: str | None = None
    source_chunk_id: str | None = None


class Relation(BaseModel):
    source: str
    target: str
    type: str
    evidence: str | None = None
    source_chunk_id: str | None = None


class Chunk(BaseModel):
    chunk_id: str
    pdf_file: str
    page: int
    text: str
    images: list[str] = Field(default_factory=list)
    formula_candidates: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    chunk_id: str
    entities: list[Entity] = Field(default_factory=list)
    relations: list[Relation] = Field(default_factory=list)
    raw_response: str | None = None


class Subgraph(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
