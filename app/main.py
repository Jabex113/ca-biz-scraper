from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import JSONResponse

from app.scraper import scrape_businesses, write_csv

app = FastAPI(title="CA Biz Scraper", version="1.0.0")


@app.get("/healthz")
def healthz() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/search")
def search(
    term: str = Query(..., min_length=1, max_length=100, description="Search term for business records"),
    limit: int = Query(500, ge=1, le=500, description="Max records to retrieve (<=500)"),
    headless: bool = Query(True, description="Run browser headless (set false for debugging)"),
):
    rows, headers = [], []
    error_msg = None
    try:
        rows, headers = scrape_businesses(term, max_records=limit, headless=headless)
    except Exception as e:
        error_msg = str(e)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = Path("data") / f"results_{term}_{ts}.csv"
    try:
        write_csv(rows, csv_path)
    except Exception:
        csv_path = Path()

    payload: Dict[str, Any] = {
        "term": term,
        "count": len(rows),
        "limit": limit,
        "table_headers": headers,
        "csv_file": str(csv_path) if str(csv_path) else None,
        "data": rows,
    }
    
    if error_msg:
        payload["error"] = error_msg

    return JSONResponse(content=payload)
