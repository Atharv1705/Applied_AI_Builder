# Applied AI Builder — DDR Report Generation System

This project turns two PDFs — an **Inspection Report** and a **Thermal Report** — into a single **Detailed Diagnostic Report (DDR)** with structured JSON, embedded images, conflict and missing-data callouts, and severity reasoning.

## What it does

1. **Loads PDFs** with PyMuPDF: plain text per page plus embedded images saved to disk.
2. **Chunks text** (configurable size/overlap) and calls the **Google Gemini** API (`response_mime_type: application/json`) to extract facts **without inventing** content not present in the source.
3. **Consolidates** chunk-level JSON per document, then **merges** inspection + thermal into one schema (areas aligned, duplicates reduced, conflicts flagged).
4. **Writes** `ddr_intermediate.json`, consolidated source JSON files, and a **client-style PDF** using ReportLab.

## Setup

```bash
cd "Applied AI Builder"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` and set `GEMINI_API_KEY` (from [Google AI Studio](https://aistudio.google.com/apikey)). You can use `GOOGLE_API_KEY` instead if you prefer. Optional: `GEMINI_MODEL` (default `gemini-2.5-flash`). Older names like `gemini-1.5-flash` may return **404** on the current API. If you see **429 / quota** or `limit: 0` on a model, try `gemini-2.5-flash`, `gemini-flash-latest`, or enable billing — see [rate limits](https://ai.google.dev/gemini-api/docs/rate-limits).

## Run

```bash
python main.py --inspection path\to\Inspection_Report.pdf --thermal path\to\Thermal_Report.pdf --out-dir output
```

Outputs (under `--out-dir`, default `output/`):

| File | Purpose |
|------|---------|
| `DDR_Report.pdf` | Final DDR for the client |
| `DDR_Report.docx` | Optional Word output (`--write-docx`) |
| `ddr_intermediate.json` | Full structured object (areas, summaries, conflicts, missing) |
| `consolidated_inspection.json` | Merged factual extraction from inspection |
| `consolidated_thermal.json` | Merged factual extraction from thermal |
| `images/` | Extracted images referenced in JSON / PDF |

Custom PDF path:

```bash
python main.py --inspection Inspection_Report.pdf --thermal Thermal_Report.pdf --report C:\Reports\Project_DDR.pdf
```

PDF + Word:

```bash
python main.py --inspection Inspection_Report.pdf --thermal Thermal_Report.pdf --write-docx --report-docx C:\Reports\Project_DDR.docx
```

## Intermediate JSON shape

The pipeline validates against `DDRIntermediate` in `ddr_builder/schema.py`. Core fields include:

- `property_summary`, `areas[]` (with `observation`, `thermal_finding`, `root_cause`, `severity`, `severity_reason`, `recommended_action`, `image_available`, `image_paths`, `conflict_note`)
- `conflicts`, `missing_information`
- Summary lists for root causes, severity bands, recommended actions, and notes

Prompts in `ddr_builder/prompts.py` instruct the model to use **“Not Available”** for absent data and to record **conflicts** explicitly.

## Project layout

| Path | Role |
|------|------|
| `main.py` | CLI entry |
| `ddr_builder/pdf_loader.py` | PyMuPDF text + image extraction |
| `ddr_builder/chunking.py` | Character-based chunking |
| `ddr_builder/llm_extract.py` | Gemini JSON extraction / merge |
| `ddr_builder/prompts.py` | Loads templates from `ddr_builder/prompt_templates/*.txt` |
| `ddr_builder/schema.py` | Pydantic `DDRIntermediate` / `AreaRecord` |
| `ddr_builder/json_extraction.py` | Load/save validated intermediate JSON |
| `ddr_builder/pipeline.py` | End-to-end orchestration |
| `ddr_builder/report_generator.py` | ReportLab DDR PDF |

## Architecture

```
PDF Loader → Text + Images
    → Chunking → LLM extraction (per doc) → Hierarchical JSON merge
    → LLM merge (inspection + thermal) → ddr_intermediate.json
    → Report generator → DDR PDF
```

## OCR (optional)

If PDFs are **scanned images** with no text layer, PyMuPDF will return little or no text. The pipeline will still run but insert a placeholder chunk warning; for production you can add **pytesseract** (and install [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) on the OS) and pre-process pages before extraction. Uncomment `pytesseract` in `requirements.txt` if you extend the loader accordingly.

## Limitations

- The LLM **does not see pixel data**; image filenames and page context are passed as text. Associate images with areas only when the report text supports that link.
- Long PDFs incur **multiple API calls** (per chunk + consolidation + final merge).
- Use a Gemini model that supports **JSON / structured MIME** responses (Flash/Pro as configured).

## License

Use and modify for your own projects as needed.
