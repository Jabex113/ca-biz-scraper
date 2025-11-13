from pathlib import Path
from typing import Any, Dict, List, Tuple
import csv
import time
import re
from contextlib import contextmanager

from playwright.sync_api import sync_playwright, BrowserContext, Page

SEARCH_URL = "https://bizfileonline.sos.ca.gov/search/business"


def write_csv(rows: List[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    headers: List[str] = sorted({k for row in rows for k in row.keys()}) if rows else []
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({h: row.get(h, "") for h in headers})


@contextmanager
def launch_browser(headless: bool = True):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
            ],
        )
        context: BrowserContext = browser.new_context(
            viewport={"width": 1366, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            java_script_enabled=True,
            locale="en-US",
            timezone_id="America/Los_Angeles",
        )
        context.route(
            re.compile(r"\.(png|jpg|jpeg|gif|webp|svg|woff2?|ttf|eot)(\?|$)", re.I),
            lambda route: route.abort(),
        )
        try:
            yield context
        finally:
            context.close()
            browser.close()


def _safe_text(el) -> str:
    try:
        return el.inner_text().strip()
    except Exception:
        return ""


def _extract_table_headers(page: Page) -> List[str]:
    headers: List[str] = []
    for sel in ["table thead tr th", "table tr th", "[role=table] thead [role=columnheader]"]:
        ths = page.locator(sel)
        if ths.count() > 0:
            headers = [ths.nth(i).inner_text().strip() for i in range(ths.count())]
            if headers:
                break
    return [h for h in headers if h]


def _extract_table_rows(page: Page) -> List[List[str]]:
    rows: List[List[str]] = []
    for sel in ["table tbody tr", "table tr", "[role=rowgroup] [role=row]"]:
        trs = page.locator(sel)
        if trs.count() == 0:
            continue
        for i in range(trs.count()):
            tr = trs.nth(i)
            if tr.locator("th").count() > 0 and tr.locator("td").count() == 0:
                continue
            cells = tr.locator("td")
            if cells.count() == 0:
                cells = tr.locator("[role=cell]")
            if cells.count() == 0:
                continue
            row = [_safe_text(cells.nth(j)) for j in range(cells.count())]
            if any(c.strip() for c in row):
                rows.append(row)
        if rows:
            break
    return rows


def _click_search(page: Page, term: str) -> None:
    filled = False
    inputs = page.locator("input[placeholder*='Search' i]")
    if inputs.count() > 0:
        try:
            inputs.first.fill(term)
            filled = True
        except Exception:
            pass
    if not filled:
        tb = page.get_by_role("textbox").first
        try:
            tb.fill(term)
            filled = True
        except Exception:
            pass
    if not filled:
        txt = page.locator("input[type=text]").first
        try:
            txt.fill(term)
            filled = True
        except Exception:
            pass
    clicked = False
    for btn in [
        page.get_by_role("button", name=re.compile("search|find|submit", re.I)).first,
        page.locator("button:has-text('Search')").first,
        page.locator("input[type=submit]").first,
    ]:
        try:
            btn.click(timeout=2000)
            clicked = True
            break
        except Exception:
            continue
    if not clicked:
        try:
            page.keyboard.press("Enter")
        except Exception:
            pass


def _collect_detail_fields(page: Page) -> Dict[str, str]:
    data: Dict[str, str] = {}
    dts = page.locator("dt")
    dds = page.locator("dd")
    if dts.count() > 0 and dds.count() >= dts.count():
        for i in range(dts.count()):
            key = dts.nth(i).inner_text().strip().rstrip(":")
            val = dds.nth(i).inner_text().strip()
            if key:
                data[key] = val
    if not data:
        rows = page.locator("table tr")
        for i in range(rows.count()):
            cells = rows.nth(i).locator("td,th")
            if cells.count() >= 2:
                k = cells.nth(0).inner_text().strip().rstrip(":")
                v = cells.nth(1).inner_text().strip()
                if k and v:
                    data[k] = v
    if not data:
        labels = page.locator("label")
        for i in range(min(labels.count(), 50)):
            try:
                k = labels.nth(i).inner_text().strip().rstrip(":")
                sib = labels.nth(i).evaluate_handle("e => e.nextElementSibling")
                if sib:
                    v = sib.evaluate("e => e.innerText") or ""
                    v = (v or "").strip()
                    if k and v:
                        data[k] = v
            except Exception:
                continue
    return data


def _open_row_detail(page: Page, row_idx: int) -> bool:
    for sel in ["table tbody tr", "table tr", "[role=rowgroup] [role=row]"]:
        rows = page.locator(sel)
        if rows.count() == 0:
            continue
        if row_idx >= rows.count():
            return False
        row = rows.nth(row_idx)
        link = row.locator("a").first
        try:
            if link.count() > 0:
                link.click(timeout=4000)
            else:
                row.click(timeout=4000)
            return True
        except Exception:
            return False
    return False


def _click_next(page: Page) -> bool:
    for selector in [
        "a[aria-label='Next']",
        "button[aria-label='Next']",
        "a:has-text('Next')",
        "button:has-text('Next')",
        "li.next a",
        "[data-testid='pagination-next']",
    ]:
        el = page.locator(selector)
        if el.count() > 0:
            try:
                el.first.click(timeout=2000)
                return True
            except Exception:
                continue
    try:
        page.get_by_role("button", name=re.compile("next|>"))
        page.keyboard.press("PageDown")
    except Exception:
        pass
    return False


def scrape_businesses(term: str, max_records: int = 500, headless: bool = True, per_page_sleep: float = 0.8) -> Tuple[List[Dict[str, Any]], List[str]]:
    results: List[Dict[str, Any]] = []
    with launch_browser(headless=headless) as context:
        page = context.new_page()
        page.set_default_timeout(15000)
        page.goto(SEARCH_URL, wait_until="domcontentloaded")
        for sel in [
            "button:has-text('Accept')",
            "button:has-text('I Agree')",
            "text=Accept All",
        ]:
            try:
                page.locator(sel).first.click(timeout=1500)
            except Exception:
                pass
        _click_search(page, term)
        table_headers: List[str] = []
        for _ in range(3):
            try:
                page.wait_for_selector("table", timeout=8000)
                table_headers = _extract_table_headers(page)
                break
            except Exception:
                time.sleep(1)
        fetched = 0
        page_index = 1
        while True:
            rows_2d = _extract_table_rows(page)
            if not rows_2d:
                break
            page_dicts: List[Dict[str, Any]] = []
            for r in rows_2d:
                if table_headers and len(r) == len(table_headers):
                    d = {table_headers[i]: r[i] for i in range(len(r))}
                else:
                    d = {f"col_{i+1}": r[i] for i in range(len(r))}
                page_dicts.append(d)
            for idx_on_page, base in enumerate(page_dicts):
                if fetched >= max_records:
                    break
                try:
                    with page.expect_navigation(wait_until="domcontentloaded", timeout=12000):
                        opened = _open_row_detail(page, idx_on_page)
                        if not opened:
                            raise RuntimeError("Could not open detail row")
                except Exception:
                    results.append(base)
                    fetched += 1
                    continue
                details: Dict[str, str] = {}
                try:
                    details = _collect_detail_fields(page)
                except Exception:
                    details = {}
                merged = {**base, **details}
                results.append(merged)
                fetched += 1
                try:
                    page.go_back(wait_until="domcontentloaded")
                    page.wait_for_selector("table", timeout=10000)
                except Exception:
                    try:
                        page.goto(SEARCH_URL, wait_until="domcontentloaded")
                        _click_search(page, term)
                        page.wait_for_selector("table", timeout=10000)
                        for _ in range(max(0, page_index - 1)):
                            _click_next(page)
                            page.wait_for_selector("table", timeout=8000)
                    except Exception:
                        return results, table_headers
            if fetched >= max_records:
                break
            moved = _click_next(page)
            if not moved:
                break
            page_index += 1
            time.sleep(per_page_sleep)
    return results, table_headers


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "1"
    data, headers = scrape_businesses(q, max_records=10, headless=False)
    out = Path("data/test.csv")
    write_csv(data, out)
    print(f"Wrote {len(data)} rows to {out}")
