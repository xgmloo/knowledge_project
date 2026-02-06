from __future__ import annotations

import json
import re
from pathlib import Path

import fitz

from .models import Chunk

FORMULA_PATTERN = re.compile(
    r"([A-Za-z]\w*\s*=\s*[^\n]+|[\d\w\s\+\-\*/\^_=<>\(\)]+(?:\\frac|\\sum|\\int)[^\n]*)"
)


class PDFParser:
    def __init__(self, image_output_dir: Path, chunk_size: int = 1200, overlap: int = 200) -> None:
        self.image_output_dir = image_output_dir
        self.chunk_size = chunk_size
        self.overlap = overlap

    def parse_pdf(self, pdf_path: Path) -> list[Chunk]:
        doc = fitz.open(pdf_path)
        all_chunks: list[Chunk] = []

        for page_index, page in enumerate(doc, start=1):
            page_text = page.get_text("text")
            image_paths = self._extract_images(page, pdf_path.stem, page_index)
            formulas = self._extract_formula_candidates(page_text)
            page_chunks = self._split_chunks(page_text)

            for idx, chunk_text in enumerate(page_chunks, start=1):
                all_chunks.append(
                    Chunk(
                        chunk_id=f"{pdf_path.stem}-p{page_index}-c{idx}",
                        pdf_file=pdf_path.name,
                        page=page_index,
                        text=chunk_text,
                        images=image_paths,
                        formula_candidates=formulas,
                    )
                )

        return all_chunks

    def parse_folder(self, pdf_dir: Path) -> list[Chunk]:
        chunks: list[Chunk] = []
        for pdf_path in sorted(pdf_dir.glob("*.pdf")):
            chunks.extend(self.parse_pdf(pdf_path))
        return chunks

    def dump_jsonl(self, chunks: list[Chunk], output_file: Path) -> None:
        with output_file.open("w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk.model_dump(), ensure_ascii=False) + "\n")

    def _extract_images(self, page: fitz.Page, pdf_stem: str, page_num: int) -> list[str]:
        images = []
        for i, image_info in enumerate(page.get_images(full=True), start=1):
            xref = image_info[0]
            pix = fitz.Pixmap(page.parent, xref)
            if pix.n - pix.alpha > 3:
                pix = fitz.Pixmap(fitz.csRGB, pix)
            image_file = self.image_output_dir / f"{pdf_stem}_p{page_num}_{i}.png"
            pix.save(image_file)
            images.append(str(image_file))
        return images

    def _extract_formula_candidates(self, text: str) -> list[str]:
        candidates = set()
        for line in text.splitlines():
            cleaned = line.strip()
            if len(cleaned) < 4:
                continue
            if FORMULA_PATTERN.search(cleaned) or sum(ch in cleaned for ch in "=+-*/^∑∫√λ") >= 2:
                candidates.add(cleaned)
        return sorted(candidates)

    def _split_chunks(self, text: str) -> list[str]:
        normalized = "\n".join(line.strip() for line in text.splitlines() if line.strip())
        if not normalized:
            return []

        chunks: list[str] = []
        start = 0
        while start < len(normalized):
            end = min(len(normalized), start + self.chunk_size)
            chunks.append(normalized[start:end])
            if end == len(normalized):
                break
            start = max(0, end - self.overlap)
        return chunks
