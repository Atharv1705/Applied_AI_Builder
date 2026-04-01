from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import fitz  # PyMuPDF


@dataclass
class ExtractedImage:
    path: Path
    page_index: int
    image_index_on_page: int
    source_pdf: str


@dataclass
class PdfExtractionResult:
    """Text and image paths extracted from one PDF."""

    source_path: Path
    full_text: str
    images: list[ExtractedImage] = field(default_factory=list)
    page_texts: list[str] = field(default_factory=list)


def _safe_stem(path: Path) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in path.stem)[:80]


def extract_pdf(
    pdf_path: str | Path,
    images_dir: Path,
    label: str,
) -> PdfExtractionResult:
    """
    Extract plain text (per-page and concatenated) and embedded images.
    Images are written under images_dir with deterministic names.
    """
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    images_dir = Path(images_dir).resolve()
    images_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    page_texts: list[str] = []
    images: list[ExtractedImage] = []
    stem = _safe_stem(pdf_path)

    try:
        for page_index in range(len(doc)):
            page = doc[page_index]
            page_texts.append(page.get_text("text") or "")
            image_list = page.get_images(full=True)
            for img_ord, img_info in enumerate(image_list):
                xref = img_info[0]
                try:
                    base = doc.extract_image(xref)
                except Exception:
                    continue
                ext = base.get("ext", "png")
                img_bytes = base.get("image")
                if not img_bytes:
                    continue
                digest = hashlib.sha256(img_bytes).hexdigest()[:12]
                fname = f"{label}_{stem}_p{page_index + 1}_i{img_ord + 1}_{digest}.{ext}"
                out_path = images_dir / fname
                if not out_path.exists():
                    out_path.write_bytes(img_bytes)
                images.append(
                    ExtractedImage(
                        path=out_path,
                        page_index=page_index,
                        image_index_on_page=img_ord,
                        source_pdf=str(pdf_path),
                    )
                )
    finally:
        doc.close()

    full_text = "\n\n".join(
        f"--- Page {i + 1} ---\n{t.strip()}" for i, t in enumerate(page_texts) if t.strip()
    )
    return PdfExtractionResult(
        source_path=pdf_path,
        full_text=full_text.strip(),
        images=images,
        page_texts=page_texts,
    )


def images_catalog_for_prompt(extraction: PdfExtractionResult, label: str, base_dir: Path | None = None) -> str:
    """Short catalog of image paths for the LLM to reference in output.

    If base_dir is provided, paths are made relative to it for portability.
    """
    if not extraction.images:
        return f"No embedded images extracted from {label} PDF."
    lines = [f"Images from {label} (use these exact paths in image_paths when relevant):"]
    for im in extraction.images:
        if base_dir is not None:
            try:
                path_str = im.path.relative_to(base_dir).as_posix()
            except ValueError:
                path_str = im.path.as_posix()
        else:
            path_str = im.path.as_posix()
        lines.append(
            f"- Page {im.page_index + 1}, image {im.image_index_on_page + 1}: {path_str}"
        )
    return "\n".join(lines)
