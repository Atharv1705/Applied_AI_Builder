#!/usr/bin/env python3
"""
CLI entry: Inspection_Report.pdf + Thermal_Report.pdf → DDR PDF + JSON.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ddr_builder.pipeline import run_pipeline
from ddr_builder.report_generator import build_ddr_docx, build_ddr_pdf


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Detailed Diagnostic Report (DDR) from inspection and thermal PDFs."
    )
    parser.add_argument(
        "--inspection",
        required=True,
        type=Path,
        help="Path to Inspection_Report.pdf",
    )
    parser.add_argument(
        "--thermal",
        required=True,
        type=Path,
        help="Path to Thermal_Report.pdf",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("output"),
        help="Working directory for images and intermediate JSON (default: ./output)",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Output DDR PDF path (default: <out-dir>/DDR_Report.pdf)",
    )
    parser.add_argument(
        "--report-docx",
        type=Path,
        default=None,
        help="Optional output .docx path (default: <out-dir>/DDR_Report.docx when --write-docx)",
    )
    parser.add_argument(
        "--write-docx",
        action="store_true",
        help="Also write a Word document alongside the PDF",
    )
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    report_path = args.report or (out_dir / "DDR_Report.pdf")

    result = run_pipeline(args.inspection, args.thermal, out_dir)
    build_ddr_pdf(result.ddr, report_path, base_dir=out_dir)
    if args.write_docx:
        docx_path = args.report_docx or (out_dir / "DDR_Report.docx")
        build_ddr_docx(result.ddr, docx_path, base_dir=out_dir)
        print(f"DDR Word: {docx_path.resolve()}")

    print(f"DDR intermediate JSON: {result.intermediate_json_path}")
    print(f"Consolidated inspection: {result.inspection_extraction_path}")
    print(f"Consolidated thermal: {result.thermal_extraction_path}")
    print(f"Images directory: {result.images_dir}")
    print(f"DDR PDF: {report_path.resolve()}")


if __name__ == "__main__":
    main()
