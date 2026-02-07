from __future__ import annotations

import json
import re

import requests

from .models import Entity, ExtractionResult, Relation

PROMPT_TEMPLATE = """
你是知识图谱抽取器。请仅根据输入教材片段文本抽取知识图谱。
输出必须是严格 JSON，不要输出 markdown。
JSON schema:
{{
  "entities": [
    {{"name": "", "type": "Concept|Person|Method|Formula|Term|Other", "description": ""}}
  ],
  "relations": [
    {{"source": "", "target": "", "type": "定义|包含|推导|应用于|相关于|前置于", "evidence": ""}}
  ]
}}
要求：
1) 只依据文本内容抽取，不要使用图片与公式候选信息。
2) 实体 name 去重，保持教材术语原文。
3) 关系中的 source/target 必须出现在 entities.name 中。
4) 如果信息不足，返回空数组而不是编造。

片段文本:
{text}
""".strip()


class OllamaExtractor:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: int = 120,
        retry_with_short_text: bool = True,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.retry_with_short_text = retry_with_short_text

    def extract(self, chunk_id: str, text: str, image_paths: list[str], formulas: list[str]) -> ExtractionResult:
        # 按用户要求：忽略图片与公式候选，仅使用文本抽取。
        _ = image_paths
        _ = formulas

        payloads = self._build_attempt_payloads(text)
        raw_text = "{}"

        for payload in payloads:
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                raw_text = response.json().get("response", "{}")
                break
            except requests.RequestException as exc:
                raw_text = self._extract_error_body(exc)
                continue

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

    def _build_attempt_payloads(self, text: str) -> list[dict[str, object]]:
        prompt = PROMPT_TEMPLATE.format(text=text)
        base_payload: dict[str, object] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        payloads = [base_payload]

        if self.retry_with_short_text and len(text) > 1200:
            short_prompt = PROMPT_TEMPLATE.format(text=text[:1200])
            payloads.append({**base_payload, "prompt": short_prompt})

        return payloads

    @staticmethod
    def _extract_error_body(exc: requests.RequestException) -> str:
        response = getattr(exc, "response", None)
        if response is None:
            return "{}"

        try:
            return response.json().get("response", "{}")
        except ValueError:
            return response.text or "{}"

    @staticmethod
    def _safe_parse_json(raw_text: str) -> dict:
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return {"entities": [], "relations": []}
