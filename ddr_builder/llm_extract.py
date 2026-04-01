from __future__ import annotations

import json
import re
import time
from typing import Any

from google import genai
from google.genai import types

from ddr_builder.config import GEMINI_API_KEY, GEMINI_MODEL, require_gemini_key
from ddr_builder.prompts import (
    DDR_MERGE_SYSTEM,
    RULES_NO_INVENTION,
    format_consolidate,
    format_ddr_merge_user,
    format_inspection_chunk,
    format_thermal_chunk,
)
from ddr_builder.schema import DDRIntermediate

_MAX_RETRIES = 4


def _client() -> genai.Client:
    require_gemini_key()
    return genai.Client(api_key=GEMINI_API_KEY)


def _response_text(response: Any) -> str:
    if response is None:
        return ""
    t = getattr(response, "text", None)
    if t:
        return t
    cands = getattr(response, "candidates", None) or []
    if not cands:
        return ""
    parts = getattr(getattr(cands[0], "content", None), "parts", None) or []
    return "".join(getattr(p, "text", "") or "" for p in parts)


def _parse_json_response(raw: str) -> dict[str, Any]:
    text = (raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    if not text:
        text = "{}"
    return json.loads(text)


def _is_rate_limit_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    code = getattr(exc, "status_code", None)
    if code == 429:
        return True
    return (
        "429" in str(exc)
        or "resource exhausted" in msg
        or "resource_exhausted" in msg
        or "quota" in msg
        or ("rate" in msg and "limit" in msg)
    )


def call_json_object(system: str, user: str, temperature: float = 0.2) -> dict[str, Any]:
    client = _client()
    last_err: BaseException | None = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=user,
                config=types.GenerateContentConfig(
                    systemInstruction=system,
                    responseMimeType="application/json",
                    temperature=temperature,
                ),
            )
            raw = _response_text(response)
            return _parse_json_response(raw)
        except Exception as e:
            last_err = e
            if _is_rate_limit_error(e) and attempt < _MAX_RETRIES - 1:
                wait = min(120, 15 * (2**attempt))
                time.sleep(wait)
                continue
            raise
    assert last_err is not None
    raise last_err


def extract_inspection_chunk(image_catalog: str, chunk: str) -> dict[str, Any]:
    user = format_inspection_chunk(RULES_NO_INVENTION, image_catalog, chunk)
    return call_json_object(
        "You output only valid JSON for inspection fact extraction.",
        user,
    )


def extract_thermal_chunk(image_catalog: str, chunk: str) -> dict[str, Any]:
    user = format_thermal_chunk(RULES_NO_INVENTION, image_catalog, chunk)
    return call_json_object(
        "You output only valid JSON for thermal fact extraction.",
        user,
    )


def consolidate_partials(partials: list[dict[str, Any]]) -> dict[str, Any]:
    if not partials:
        return {"property_details": "Not Available", "areas": [], "missing_information": []}
    if len(partials) == 1:
        return partials[0]
    payload = json.dumps(partials, ensure_ascii=False, indent=2)
    user = format_consolidate(payload)
    return call_json_object(
        "You merge JSON fragments without inventing facts. Output only JSON.",
        user,
    )


def hierarchical_consolidate(
    partials: list[dict[str, Any]],
    max_batch: int = 8,
) -> dict[str, Any]:
    """Merge many chunk-level dicts in batches to limit prompt size."""
    if not partials:
        return {"property_details": "Not Available", "areas": [], "missing_information": []}
    layer = partials[:]
    while len(layer) > 1:
        nxt: list[dict[str, Any]] = []
        for i in range(0, len(layer), max_batch):
            batch = layer[i : i + max_batch]
            nxt.append(consolidate_partials(batch))
        layer = nxt
    return layer[0]


def map_thermal_areas(
    thermal_areas: list[str],
    inspection_areas: list[str],
) -> dict[str, str]:
    """Use LLM to map thermal area names to inspection area names.

    Returns a dict: {thermal_area_name: inspection_area_name or "Unknown"}.
    Falls back to a simple keyword heuristic if the LLM call fails.
    """
    if not thermal_areas or not inspection_areas:
        return {}

    system = (
        "You are a building inspection assistant. "
        "Map thermal report area names to inspection report area names based on "
        "description, location hints, or logical similarity. "
        "Return ONLY a JSON object where keys are thermal area names and values are "
        "the best matching inspection area name. If no match, use \"Unknown\"."
    )
    user = (
        f"Thermal areas: {json.dumps(thermal_areas)}\n"
        f"Inspection areas: {json.dumps(inspection_areas)}\n"
        "Return JSON mapping thermal → inspection area names."
    )
    try:
        result = call_json_object(system, user, temperature=0.1)
        # Validate: all keys should be thermal area names
        mapping = {str(k): str(v) for k, v in result.items() if k in thermal_areas}
        # Fill any missing thermal areas with Unknown
        for ta in thermal_areas:
            if ta not in mapping:
                mapping[ta] = _keyword_map(ta, inspection_areas)
        return mapping
    except Exception:
        # Fallback: keyword heuristic
        return {ta: _keyword_map(ta, inspection_areas) for ta in thermal_areas}


def _keyword_map(thermal_area: str, inspection_areas: list[str]) -> str:
    """Simple keyword-based fallback mapping."""
    ta_lower = thermal_area.lower()
    keywords = {
        "hall": ["hall", "corridor", "lobby", "entrance", "foyer"],
        "bedroom": ["bedroom", "bed", "room", "sleeping"],
        "kitchen": ["kitchen", "cook", "pantry"],
        "bathroom": ["bathroom", "bath", "toilet", "wc", "washroom"],
        "external": ["external", "exterior", "outside", "facade", "wall"],
        "parking": ["parking", "garage", "car", "basement"],
    }
    for insp_area in inspection_areas:
        ia_lower = insp_area.lower()
        for key, synonyms in keywords.items():
            if any(s in ta_lower for s in synonyms) and any(s in ia_lower for s in synonyms):
                return insp_area
    # Try direct substring match
    for insp_area in inspection_areas:
        if insp_area.lower() in ta_lower or ta_lower in insp_area.lower():
            return insp_area
    return "Unknown"


def _merge_duplicate_areas(areas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge areas with the same area_name (case-insensitive) into one entry.

    Text fields are joined with '; ' (deduplicating identical values).
    List fields (image_paths, issues, etc.) are unioned and deduplicated.
    """
    seen: dict[str, dict[str, Any]] = {}  # normalised key → merged area dict
    order: list[str] = []  # preserve first-seen order

    for area in areas:
        raw_name = area.get("area_name", "") or ""
        key = raw_name.strip().lower()
        if not key:
            continue
        if key not in seen:
            seen[key] = dict(area)
            order.append(key)
        else:
            base = seen[key]
            for field, val in area.items():
                if field == "area_name":
                    continue
                if isinstance(val, list):
                    existing = base.get(field) or []
                    if isinstance(existing, str):
                        existing = [existing] if existing else []
                    combined = existing + [v for v in val if v not in existing]
                    base[field] = combined
                elif isinstance(val, str) and val and val != "Not Available":
                    existing = base.get(field, "") or ""
                    if not existing or existing == "Not Available":
                        base[field] = val
                    elif val not in existing:
                        base[field] = f"{existing}; {val}"

    return [seen[k] for k in order]


def apply_thermal_area_mapping(
    thermal: dict[str, Any],
    inspection: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Remap thermal area names to match inspection area names.

    Returns the updated thermal dict and a list of mapping notes for missing_information.
    """
    thermal_areas_raw = [a.get("area_name", "") for a in (thermal.get("areas") or []) if a.get("area_name")]
    inspection_areas_raw = [a.get("area_name", "") for a in (inspection.get("areas") or []) if a.get("area_name")]

    if not thermal_areas_raw or not inspection_areas_raw:
        return thermal, []

    # Filter out areas with no real name — treat them as unmapped general thermal data
    valid_thermal_areas = [ta for ta in thermal_areas_raw if ta.strip().lower() != "not available"]
    invalid_thermal_areas = [ta for ta in thermal_areas_raw if ta.strip().lower() == "not available"]

    notes: list[str] = []

    # Add a single consolidated note for all unnamed thermal areas (avoid 30 duplicate lines)
    if invalid_thermal_areas:
        notes.append(
            f"Thermal report contains {len(invalid_thermal_areas)} area(s) with no location name — "
            "thermal readings exist but cannot be mapped to specific inspection areas. "
            "General thermal data has been noted in the property summary."
        )

    if not valid_thermal_areas:
        # No mappable thermal areas at all — return thermal as-is with the note
        return thermal, notes

    mapping = map_thermal_areas(valid_thermal_areas, inspection_areas_raw)

    updated_areas = []
    for area in (thermal.get("areas") or []):
        ta = area.get("area_name", "")
        if ta.strip().lower() == "not available":
            # Skip unmapped areas — already noted above
            continue
        mapped = mapping.get(ta, "Unknown")
        new_area = dict(area)
        if mapped == "Unknown":
            notes.append(
                f"Thermal area '{ta}' could not be mapped to any inspection area — "
                "thermal findings for this area may not appear in the DDR."
            )
        else:
            new_area["area_name"] = mapped
            new_area["_original_thermal_area"] = ta
        updated_areas.append(new_area)

    # Merge any areas that now share the same name after remapping
    updated_thermal = dict(thermal)
    updated_thermal["areas"] = _merge_duplicate_areas(updated_areas)
    return updated_thermal, notes


def merge_to_ddr(
    inspection: dict[str, Any],
    thermal: dict[str, Any],
    inspection_catalog: str,
    thermal_catalog: str,
) -> DDRIntermediate:
    # Map thermal area names to inspection area names before merging
    thermal_mapped, mapping_notes = apply_thermal_area_mapping(thermal, inspection)

    user = format_ddr_merge_user(
        json.dumps(inspection, ensure_ascii=False, indent=2),
        json.dumps(thermal_mapped, ensure_ascii=False, indent=2),
        inspection_catalog,
        thermal_catalog,
    )
    data = call_json_object(
        DDR_MERGE_SYSTEM.format(rules=RULES_NO_INVENTION), user, temperature=0.3
    )
    normalized = _normalize_ddr_dict(data)

    # Inject thermal mapping notes into missing_information (deduplicated)
    if mapping_notes:
        existing = normalized.get("missing_information") or []
        seen = set(existing)
        for note in mapping_notes:
            if note not in seen:
                existing.append(note)
                seen.add(note)
        normalized["missing_information"] = existing

    return DDRIntermediate.model_validate(normalized)


def _normalize_ddr_dict(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce common LLM quirks into DDRIntermediate-compatible shapes."""
    out = dict(data)
    areas_raw = out.get("areas") or []
    areas = []
    for a in areas_raw:
        if not isinstance(a, dict):
            continue
        ia = a.get("image_available", "No")
        if ia not in ("Yes", "No"):
            ia = "Yes" if str(ia).lower() in ("yes", "true", "1") else "No"
        img_paths = a.get("image_paths") or []
        if isinstance(img_paths, str):
            img_paths = [img_paths] if img_paths else []
        areas.append(
            {
                "area_name": str(a.get("area_name", "") or "Not Available"),
                "observation": str(a.get("observation", "") or "Not Available"),
                "thermal_finding": str(a.get("thermal_finding", "") or "Not Available"),
                "root_cause": str(a.get("root_cause", "") or "Not Available"),
                "severity": str(a.get("severity", "") or "Not Available"),
                "severity_reason": str(a.get("severity_reason", "") or "Not Available"),
                "recommended_action": str(a.get("recommended_action", "") or "Not Available"),
                "image_available": ia,
                "image_paths": [str(p) for p in img_paths],
                "conflict_note": str(a.get("conflict_note", "") or ""),
            }
        )
    out["areas"] = areas

    # Deduplicate areas that share the same name (LLM sometimes emits duplicates)
    out["areas"] = _merge_duplicate_areas(out["areas"])

    for key in (
        "conflicts",
        "missing_information",
        "root_causes_summary",
        "high_severity",
        "medium_severity",
        "low_severity",
        "immediate_actions",
        "preventive_actions",
        "further_investigation",
        "additional_notes",
    ):
        v = out.get(key) or []
        if isinstance(v, str):
            v = [v] if v else []
        items = [str(x) for x in v]
        # Deduplicate while preserving order
        seen_items: set[str] = set()
        deduped: list[str] = []
        for item in items:
            # Truncate very long single items (e.g. raw temperature dumps)
            if len(item) > 300:
                item = item[:297] + "..."
            if item not in seen_items:
                seen_items.add(item)
                deduped.append(item)
        out[key] = deduped

    out["property_summary"] = str(out.get("property_summary", "") or "Not Available")
    return out
