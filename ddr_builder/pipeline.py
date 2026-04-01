from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ddr_builder.chunking import chunk_text
from ddr_builder.config import CHUNK_MAX_CHARS, CHUNK_OVERLAP
from ddr_builder.llm_extract import (
    extract_inspection_chunk,
    extract_thermal_chunk,
    hierarchical_consolidate,
    merge_to_ddr,
)
from ddr_builder.pdf_loader import (
    PdfExtractionResult,
    extract_pdf,
    images_catalog_for_prompt,
)
from ddr_builder.schema import DDRIntermediate


@dataclass
class PipelineOutput:
    ddr: DDRIntermediate
    intermediate_json_path: Path
    images_dir: Path
    inspection_extraction_path: Path
    thermal_extraction_path: Path


def _chunks_or_placeholder(text: str, label: str) -> list[str]:
    chunks = chunk_text(text, CHUNK_MAX_CHARS, CHUNK_OVERLAP)
    if not chunks:
        return [f"[No extractable text from {label} PDF — document may be scanned; consider OCR.]"]
    return chunks


def _repair_image_paths(ddr: DDRIntermediate, images_dir: Path, work_dir: Path) -> DDRIntermediate:
    """
    Rewrite stale or absolute image paths to relative paths from work_dir when possible.
    Keeps existing valid relative paths unchanged.
    """
    if not ddr.areas:
        return ddr

    images_dir = images_dir.resolve()
    work_dir = work_dir.resolve()

    for area in ddr.areas:
        fixed_paths: list[str] = []
        for raw in area.image_paths:
            raw_path = Path(raw)
            # Try as-is (may already be relative and valid)
            if raw_path.is_file():
                try:
                    fixed_paths.append(raw_path.relative_to(work_dir).as_posix())
                except ValueError:
                    fixed_paths.append(raw_path.as_posix())
                continue
            # Try resolving against work_dir
            candidate_abs = (work_dir / raw_path).resolve()
            if candidate_abs.is_file():
                try:
                    fixed_paths.append(candidate_abs.relative_to(work_dir).as_posix())
                except ValueError:
                    fixed_paths.append(candidate_abs.as_posix())
                continue
            # Try by filename in images_dir
            candidate = images_dir / raw_path.name
            if candidate.is_file():
                try:
                    fixed_paths.append(candidate.relative_to(work_dir).as_posix())
                except ValueError:
                    fixed_paths.append(candidate.as_posix())
                continue
            # Preserve unresolved entries for transparency/debugging.
            fixed_paths.append(raw)
        area.image_paths = fixed_paths
        if area.image_paths and area.image_available == "No":
            area.image_available = "Yes"
    return ddr


def run_pipeline(
    inspection_pdf: str | Path,
    thermal_pdf: str | Path,
    work_dir: str | Path,
) -> PipelineOutput:
    """
    Full pipeline: load PDFs → extract text/images → chunk LLM → merge → DDR JSON.
    """
    work_dir = Path(work_dir).resolve()
    images_dir = work_dir / "images"
    work_dir.mkdir(parents=True, exist_ok=True)

    inspection_pdf = Path(inspection_pdf).resolve()
    thermal_pdf = Path(thermal_pdf).resolve()

    ins_ex = extract_pdf(inspection_pdf, images_dir, "inspection")
    th_ex = extract_pdf(thermal_pdf, images_dir, "thermal")

    ins_catalog = images_catalog_for_prompt(ins_ex, "Inspection", base_dir=work_dir)
    th_catalog = images_catalog_for_prompt(th_ex, "Thermal", base_dir=work_dir)

    ins_partials: list[dict[str, Any]] = []
    for ch in _chunks_or_placeholder(ins_ex.full_text, "inspection"):
        ins_partials.append(extract_inspection_chunk(ins_catalog, ch))
    ins_cons = hierarchical_consolidate(ins_partials)

    th_partials: list[dict[str, Any]] = []
    for ch in _chunks_or_placeholder(th_ex.full_text, "thermal"):
        th_partials.append(extract_thermal_chunk(th_catalog, ch))
    th_cons = hierarchical_consolidate(th_partials)

    ins_path = work_dir / "consolidated_inspection.json"
    th_path = work_dir / "consolidated_thermal.json"
    ins_path.write_text(json.dumps(ins_cons, ensure_ascii=False, indent=2), encoding="utf-8")
    th_path.write_text(json.dumps(th_cons, ensure_ascii=False, indent=2), encoding="utf-8")

    ddr = merge_to_ddr(ins_cons, th_cons, ins_catalog, th_catalog)
    ddr = _repair_image_paths(ddr, images_dir, work_dir)

    ddr_path = work_dir / "ddr_intermediate.json"
    ddr_path.write_text(ddr.model_dump_json(indent=2), encoding="utf-8")

    return PipelineOutput(
        ddr=ddr,
        intermediate_json_path=ddr_path,
        images_dir=images_dir,
        inspection_extraction_path=ins_path,
        thermal_extraction_path=th_path,
    )


def extraction_results_for_debug(
    inspection_pdf: str | Path,
    thermal_pdf: str | Path,
    work_dir: str | Path,
) -> tuple[PdfExtractionResult, PdfExtractionResult]:
    work_dir = Path(work_dir).resolve()
    images_dir = work_dir / "images"
    return (
        extract_pdf(inspection_pdf, images_dir, "inspection"),
        extract_pdf(thermal_pdf, images_dir, "thermal"),
    )
