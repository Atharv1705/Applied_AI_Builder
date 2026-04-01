from typing import Literal

from pydantic import BaseModel, Field


class AreaRecord(BaseModel):
    area_name: str = ""
    observation: str = ""
    thermal_finding: str = ""
    root_cause: str = ""
    severity: str = ""
    severity_reason: str = ""
    recommended_action: str = ""
    image_available: Literal["Yes", "No"] = "No"
    image_paths: list[str] = Field(default_factory=list)
    conflict_note: str = ""


class DDRIntermediate(BaseModel):
    """Structured intermediate output before final narrative report."""

    property_summary: str = ""
    areas: list[AreaRecord] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    root_causes_summary: list[str] = Field(default_factory=list)
    high_severity: list[str] = Field(default_factory=list)
    medium_severity: list[str] = Field(default_factory=list)
    low_severity: list[str] = Field(default_factory=list)
    immediate_actions: list[str] = Field(default_factory=list)
    preventive_actions: list[str] = Field(default_factory=list)
    further_investigation: list[str] = Field(default_factory=list)
    additional_notes: list[str] = Field(default_factory=list)
