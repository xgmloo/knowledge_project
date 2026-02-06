from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import requests

from .models import Entity, ExtractionResult, Relation

PROMPT_TEMPLATE = """
你是知识图谱抽取器。请根据输入教材片段（文本、图片、公式候选）抽取知识图谱。
输出必须是严格 JSON，不要输出 markdown。
JSON schema:
{
  "entities": [
    {"name": "", "type": "Concept|Person|Method|Formula|Term|Other", "description": ""}
  ],
  "relations": [
    {"source": "", "target": "", "type": "定义|包含|推导|应用于|相关于|前置于", "evidence": ""}
  ]
}
要求：
1) 实体 name 去重，保持教材术语原文。
2) 关系中的 source/target 必须出现在 entities.name 中。
3) 如果信息不足，返回空数组而不是编造。

片段文本:
{text}

公式候选:
{formulas}
""".strip()


class OllamaExtractor:
    def __init__(self, base_url: str, model: str, timeout: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def extract(self, chunk_id: str, text: str, image_paths: list[str], formulas: list[str]) -> ExtractionResult:
        payload = {
            "model": self.model,
            "prompt": PROMPT_TEMPLATE.format(text=text, formulas="\n".join(formulas[:20])),
            "stream": False,
            "format": "json",
            "images": [self._encode_image(Path(p)) for p in image_paths[:4]],
        }

        response = requests.post(
            f"{self.base_url}/api/generate",
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        raw_text = response.json().get("response", "{}")

        parsed = self._safe_parse_json(raw_text)
        entities = [Entity(**item, source_chunk_id=chunk_id) for item in parsed.get("entities", []) if item.get("name")]
        name_set = {e.name for e in entities}
        relations = []
        for item in parsed.get("relations", []):
            if item.get("source") in name_set and item.get("target") in name_set and item.get("type"):
                relations.append(Relation(**item, source_chunk_id=chunk_id))

        return ExtractionResult(
            chunk_id=chunk_id,
            entities=entities,
            relations=relations,
            raw_response=raw_text,
        )

    @staticmethod
    def _encode_image(path: Path) -> str:
        return base64.b64encode(path.read_bytes()).decode("utf-8")

    @staticmethod
    def _safe_parse_json(raw_text: str) -> dict:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"entities": [], "relations": []}
