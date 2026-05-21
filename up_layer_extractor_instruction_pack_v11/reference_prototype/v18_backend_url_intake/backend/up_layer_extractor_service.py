from __future__ import annotations

import hashlib
import os
import tempfile
import urllib.parse
from pathlib import Path
from typing import Any

import fitz
import requests
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl

TYPE_CODE = {"STAV": "1", "NAVRH": "2"}

app = FastAPI(title="UP Layer Extractor Prototype Backend", version="0.18.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ExtractRequest(BaseModel):
    url: HttpUrl
    profile_id: str | None = None

def normalize_url(url: str) -> str:
    parts = urllib.parse.urlsplit(url.strip())
    if parts.scheme not in {"http", "https"}:
        raise ValueError("Only http/https PDF URLs are supported")
    path = urllib.parse.quote(urllib.parse.unquote(parts.path), safe="/%")
    query = urllib.parse.quote(urllib.parse.unquote(parts.query), safe="=&?/%:+")
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))

def download_pdf(url: str, out_dir: Path) -> Path:
    normalized = normalize_url(url)
    out = out_dir / (hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16] + ".pdf")
    headers = {"User-Agent": "UPLayerExtractor/0.18 (+server-side PDF fetch)"}
    with requests.get(normalized, headers=headers, timeout=60, stream=True) as r:
        r.raise_for_status()
        ctype = r.headers.get("content-type", "").lower()
        if "pdf" not in ctype and not normalized.lower().endswith(".pdf"):
            raise HTTPException(415, f"URL did not look like PDF: content-type={ctype!r}")
        with out.open("wb") as f:
            for chunk in r.iter_content(1024 * 256):
                if chunk:
                    f.write(chunk)
    if out.stat().st_size < 1024:
        raise HTTPException(422, "Downloaded PDF is suspiciously small")
    return out

def page_score(page: fitz.Page) -> int:
    upper = (page.get_text("text") or "").upper()
    score = 0
    for token in ["HLAVNÍ VÝKRES", "HLAVNI VYKRES", "ÚPLNÉ ZNĚNÍ", "UPLNE ZNENI", "Z12"]:
        if token in upper:
            score += 10
    try:
        score += min(len(page.get_drawings()) // 100, 10)
    except Exception:
        pass
    return score

def is_closed_ring(points: list[list[float]]) -> bool:
    if len(points) < 4:
        return False
    x0, y0 = points[0]
    x1, y1 = points[-1]
    return abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6

def path_bbox(points: list[list[float]]) -> list[float]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return [min(xs), min(ys), max(xs), max(ys)]

def style_hex(fill: Any) -> str | None:
    if not fill:
        return None
    try:
        r, g, b = fill[:3]
        return "#%02x%02x%02x" % (round(r * 255), round(g * 255), round(b * 255))
    except Exception:
        return None

def extract_vector_candidates(pdf_path: Path, source_url: str | None = None) -> dict[str, Any]:
    doc = fitz.open(pdf_path)
    if doc.page_count == 0:
        raise HTTPException(422, "PDF has no pages")
    scored = sorted([(page_score(doc[i]), i) for i in range(doc.page_count)], reverse=True)
    page_index = scored[0][1]
    page = doc[page_index]
    drawings = page.get_drawings()
    features = []
    fid = 1
    style_counts: dict[str, int] = {}
    for draw in drawings:
        fill_hex = style_hex(draw.get("fill"))
        if not fill_hex:
            continue
        for item in draw.get("items", []):
            pts: list[list[float]] = []
            if item[0] == "re":
                rect = item[1]
                pts = [[rect.x0, rect.y0], [rect.x1, rect.y0], [rect.x1, rect.y1], [rect.x0, rect.y1], [rect.x0, rect.y0]]
            else:
                continue
            if len(pts) < 4:
                continue
            if not is_closed_ring(pts):
                pts.append(pts[0])
            style_counts[fill_hex] = style_counts.get(fill_hex, 0) + 1
            props = {
                "FID": fid,
                "LAYER": "UNCLASSIFIED",
                "CLASS": "UNMAPPED",
                "TYPE": "UNMAPPED",
                "LAYER_CLASS": "UNCLASSIFIED.UNMAPPED",
                "class_type": "UNMAPPED.0",
                "text_id": None,
                "IS_CLOSED": True,
                "source_style_hex": fill_hex,
                "classification_status": "candidate_requires_profile_or_legend_mapping",
                "source_url": source_url,
                "source_pdf": pdf_path.name,
                "page": page_index + 1,
                "bbox_page_pt": path_bbox(pts),
            }
            features.append({"type": "Feature", "id": f"fid-{fid:04d}", "properties": props, "geometry": {"type": "Polygon", "coordinates": [pts]}})
            fid += 1
    return {
        "type": "FeatureCollection",
        "name": pdf_path.stem + "_vector_candidates_pagecoords",
        "source_url": source_url,
        "coordinate_system": "PDF_PAGE_POINTS_Y_DOWN_NO_CRS",
        "page_width_pt": page.rect.width,
        "page_height_pt": page.rect.height,
        "selected_page": page_index + 1,
        "page_count": doc.page_count,
        "vector_drawings_count": len(drawings),
        "style_counts": style_counts,
        "features": features,
        "warning": "Candidate extraction only. Do not treat as final RZVP/ZMEN classification until style legend/profile mapping passes.",
    }

@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "up-layer-extractor", "version": "0.18.0"}

@app.post("/api/extract")
def extract(req: ExtractRequest) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        pdf = download_pdf(str(req.url), Path(tmp))
        return extract_vector_candidates(pdf, source_url=str(req.url))

@app.post("/api/extract_upload")
async def extract_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(415, "Upload must be a PDF")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "upload.pdf"
        out.write_bytes(await file.read())
        return extract_vector_candidates(out, source_url=f"upload:{file.filename}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8787")))
