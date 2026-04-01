"""Prompt templates for extraction, consolidation, and DDR synthesis."""

from pathlib import Path

_TPL = Path(__file__).resolve().parent / "prompt_templates"


def _load_template(filename: str) -> str:
    path = _TPL / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing prompt template: {path}")
    return path.read_text(encoding="utf-8").strip()


RULES_NO_INVENTION = _load_template("rules_no_invention.txt")
EXTRACTION_INSPECTION_CHUNK = _load_template("extraction_inspection.txt")
EXTRACTION_THERMAL_CHUNK = _load_template("extraction_thermal.txt")
CONSOLIDATE_SAME_SOURCE = _load_template("consolidate_same_source.txt")
DDR_MERGE_SYSTEM = _load_template("ddr_merge_system.txt")


def format_inspection_chunk(rules: str, image_catalog: str, text: str) -> str:
    return EXTRACTION_INSPECTION_CHUNK.format(
        rules=rules, image_catalog=image_catalog, text=text
    )


def format_thermal_chunk(rules: str, image_catalog: str, text: str) -> str:
    return EXTRACTION_THERMAL_CHUNK.format(
        rules=rules, image_catalog=image_catalog, text=text
    )


def format_consolidate(partials_json: str) -> str:
    return CONSOLIDATE_SAME_SOURCE.format(rules=RULES_NO_INVENTION, partials_json=partials_json)


def format_ddr_merge_user(
    inspection_json: str,
    thermal_json: str,
    inspection_images_note: str,
    thermal_images_note: str,
) -> str:
    return f"""CONSOLIDATED INSPECTION JSON:
{inspection_json}

CONSOLIDATED THERMAL JSON:
{thermal_json}

INSPECTION IMAGE PATHS NOTE:
{inspection_images_note}

THERMAL IMAGE PATHS NOTE:
{thermal_images_note}
"""
