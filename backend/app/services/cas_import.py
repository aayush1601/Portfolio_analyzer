"""Import mutual fund holdings from a CAS (Consolidated Account Statement) PDF.

CAMS, KFintech and MF Central email a CAS listing every folio across fund houses, locked with the investor's
PAN. We parse it in memory with casparser and keep only scheme code, units and cost: the PDF, PAN, name,
email and folio numbers are never stored or logged.

Funds outside the research universe are registered on import (metadata + NAV history from mfapi.in) so the
portfolio can be valued and risk-rated; their look-through still needs holdings disclosures.
"""

import io
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import httpx
import pandas as pd

from app.services.market_data import save
from app.services.nav_data import load_navs, parse_mfapi

log = logging.getLogger(__name__)
MAX_PDF_BYTES = 10 * 1024 * 1024
TOKEN_TTL_S = 15 * 60


class CASImportError(ValueError):
    """User-facing problem with the statement (wrong password, not a CAS, nothing to import)."""


@dataclass
class ImportedFund:
    scheme_code: str
    name: str
    units: float
    cost: float | None  # total invested per the statement; None when the statement has no cost
    value: float  # statement valuation
    valuation_date: str


def parse_cas(data: bytes, password: str) -> dict:
    """casparser output as a dict; raises CASImportError with a message the user can act on."""
    import casparser
    from casparser.exceptions import CASParseError, IncorrectPasswordError

    if len(data) > MAX_PDF_BYTES:
        raise CASImportError("That file is over 10 MB; a CAS is usually well under 1 MB.")
    if not data.startswith(b"%PDF"):
        raise CASImportError("That isn't a PDF. Upload the CAS PDF exactly as it was emailed to you.")
    try:
        return casparser.read_cas_pdf(io.BytesIO(data), password, output="dict")
    except IncorrectPasswordError as e:
        raise CASImportError("Couldn't open the PDF: the password is usually your PAN in capitals.") from e
    except CASParseError as e:
        # casparser only knows watermarked CAMS/KFin statements and NSDL/CDSL; MF Central's summary is ours.
        pages = _pdf_text(data, password)
        if "MFCentralCASSummary" in "".join(pages):
            with httpx.Client(timeout=30) as client:
                return parse_mfcentral_summary(pages, client)
        raise CASImportError(
            "This PDF doesn't look like a CAMS / KFintech / MF Central consolidated statement."
        ) from e


def _pdf_text(data: bytes, password: str) -> list[str]:
    import pypdfium2 as pdfium

    try:
        doc = pdfium.PdfDocument(data, password=password or None)
    except pdfium.PdfiumError:
        return []
    return [p.get_textpage().get_text_bounded() for p in doc]


# MF Central "Consolidated Account Summary": one row per holding, both the SoA and Demat tables:
# <scheme> <invested> <market value> <gain, (x) if negative> (<+x%>) <folio> <units> <NAV date> <NAV>
_NUM = r"[\d,]+\.\d+"
_MFC_ROW = re.compile(
    rf"(?P<name>\S.*?)\s+(?P<cost>{_NUM})\s+(?P<value>{_NUM})\s+\(?{_NUM}\)?\s+\([+-]?[\d.]+%\)\s+\S+\s+"
    rf"(?P<units>{_NUM})\s+(?P<date>\d{{2}}-[A-Za-z]{{3}}-\d{{4}})\s+(?P<nav>{_NUM})"
)


def _num(s: str) -> float:
    return float(s.replace(",", ""))


def parse_mfcentral_summary(pages: list[str], client: httpx.Client) -> dict:
    """MF Central summary → the casparser dict shape funds_from_cas reads.

    The summary prints scheme names but no AMFI code or ISIN, so each name is resolved by resolve_amfi.
    """
    schemes = []
    for page in pages:
        if "Scheme Details" not in page:
            continue
        table = " ".join(page.split("NAV Date NAV", 1)[-1].split("Total ", 1)[0].split())
        for m in _MFC_ROW.finditer(table):
            nav_date = datetime.strptime(m["date"], "%d-%b-%Y").date()
            schemes.append(
                {
                    "scheme": m["name"],
                    "amfi": resolve_amfi(m["name"], nav_date, _num(m["nav"]), client),
                    "close": _num(m["units"]),
                    "valuation": {
                        "date": str(nav_date),
                        "nav": _num(m["nav"]),
                        "value": _num(m["value"]),
                        "cost": _num(m["cost"]),
                    },
                }
            )
    as_on = re.search(r"As on Date:\s*(\d{2}-[A-Za-z]{3}-\d{4})", pages[0] if pages else "")
    return {"statement_period": {"to": as_on[1] if as_on else ""}, "folios": [{"schemes": schemes}]}


_FILLER = re.compile(r"\b(plan|option|fund|scheme)\b|[^a-z0-9]")


def resolve_amfi(name: str, nav_date: date, nav: float, client: httpx.Client) -> str | None:
    """AMFI code for a scheme name: shortlist same-AMC, same plan/option names from casparser-isin's DB,
    then accept the first whose mfapi NAV on nav_date matches the statement's. None when nothing matches,
    so the fund is reported as skipped, never guessed."""
    from casparser_isin.mf_isin import MFISINDb
    from rapidfuzz import fuzz, process

    low = name.lower()
    direct, idcw = "direct" in low, bool(re.search(r"idcw|dividend", low))
    with MFISINDb() as db:
        rows = db.run_query(
            "SELECT DISTINCT name, amfi_code FROM scheme WHERE name LIKE :amc AND amfi_code != ''",
            {"amc": low.split()[0] + " %"},
        )
    names = {
        r["name"]: r["amfi_code"]
        for r in rows
        if ("direct" in r["name"].lower()) == direct
        and bool(re.search(r"idcw|dividend", r["name"].lower())) == idcw
    }
    key = lambda s: _FILLER.sub("", s.lower())  # noqa: E731  "Flexi Cap" == "FLEXICAP"
    for _, _, cand in process.extract(key(name), {n: key(n) for n in names}, scorer=fuzz.ratio, limit=5):
        code = names[cand]
        resp = client.get(f"https://api.mfapi.in/mf/{code}")
        resp.raise_for_status()
        day = nav_date.strftime("%d-%m-%Y")
        if any(
            p["date"] == day and abs(float(p["nav"]) - nav) <= 0.002 * nav
            for p in resp.json().get("data", [])
        ):
            return code
    return None


def funds_from_cas(cas: dict) -> tuple[list[ImportedFund], list[str]]:
    """Aggregate schemes across folios by AMFI code; skip closed (zero-unit) schemes.

    Returns (funds, skipped scheme names). A scheme without an AMFI code is reported, never guessed.
    """
    agg: dict[str, ImportedFund] = {}
    skipped = []
    for folio in cas.get("folios", []):
        for s in folio.get("schemes", []):
            units = float(s.get("close") or 0)
            if units <= 0:
                continue
            code = str(s.get("amfi") or "").strip()
            if not code.isdigit():
                skipped.append(s.get("scheme", "unknown scheme"))
                continue
            v = s.get("valuation") or {}
            cost = float(v["cost"]) if v.get("cost") not in (None, "") else None
            if code in agg:
                f = agg[code]
                f.units += units
                f.value += float(v.get("value") or 0)
                f.cost = None if f.cost is None or cost is None else f.cost + cost
            else:
                agg[code] = ImportedFund(
                    scheme_code=code,
                    name=str(s.get("scheme", "")).strip(),
                    units=units,
                    cost=cost,
                    value=float(v.get("value") or 0),
                    valuation_date=str(v.get("date", "")),
                )
    return list(agg.values()), skipped


# ---------- funds outside the research universe ----------
def registry_path(data_dir: Path) -> Path:
    return data_dir / "processed" / "extra_funds.json"


def load_registry(data_dir: Path) -> dict[str, dict]:
    f = registry_path(data_dir)
    return json.loads(f.read_text()) if f.exists() else {}


def register_funds(codes: list[str], data_dir: Path, client: httpx.Client) -> dict[str, dict]:
    """Fetch metadata and NAV history for new scheme codes; append NAVs to the store. Returns the registry."""
    reg = load_registry(data_dir)
    frames = []
    for code in codes:
        if code in reg:
            continue
        resp = client.get(f"https://api.mfapi.in/mf/{code}")
        resp.raise_for_status()
        payload = resp.json()
        meta = payload.get("meta") or {}
        if not payload.get("data"):
            raise CASImportError(f"No NAV history is available for scheme {code}.")
        reg[code] = {
            "scheme_code": code,
            "name": str(meta.get("scheme_name", code)),
            "amc": str(meta.get("fund_house", "")),
            "category": str(meta.get("scheme_category", "")).replace("Equity Scheme - ", ""),
        }
        frames.append(parse_mfapi(payload, code))
    if frames:
        nav_dir = data_dir / "processed" / "nav"
        try:
            existing = load_navs(data_dir)
        except FileNotFoundError:
            existing = pd.DataFrame()
        merged = pd.concat([existing, *frames], ignore_index=True).drop_duplicates(
            ["scheme_code", "date"], keep="last"
        )
        save(merged, nav_dir)
        f = registry_path(data_dir)
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(reg, indent=2))
        log.info("funds registered", extra={"fields": {"count": len(frames)}})
    return reg


# ---------- phone hand-off tokens (short-lived) ----------
# Locally they live in memory. On AWS the laptop, the phone and the polling can each reach a different Lambda
# container, so tokens live in the UserData table (PK = IMPORT#<token>, DynamoDB TTL on `expires`).
_tokens: dict[str, dict] = {}


def _table():
    from app.config import get_settings

    s = get_settings()
    if s.storage != "s3":
        return None
    import boto3

    return boto3.resource("dynamodb").Table(s.ddb_table)


def _get(token: str) -> dict | None:
    table = _table()
    if table is None:
        return _tokens.get(token)
    item = table.get_item(Key={"PK": f"IMPORT#{token}", "SK": "TOKEN"}).get("Item")
    if not item:
        return None
    return {
        "expires": float(item["expires"]),
        "owner": item.get("owner", "local"),
        "portfolio_id": item.get("portfolio_id"),
    }


def _put(token: str, value: dict) -> None:
    table = _table()
    if table is None:
        _tokens[token] = value
        return
    from decimal import Decimal

    item = {
        "PK": f"IMPORT#{token}",
        "SK": "TOKEN",
        "expires": Decimal(int(value["expires"])),
        "owner": value.get("owner", "local"),
    }
    if value.get("portfolio_id"):
        item["portfolio_id"] = value["portfolio_id"]
    table.put_item(Item=item)


def new_token(owner: str = "local") -> str:
    """owner: the signed-in user who opened the session. The phone that uploads with this token carries no
    login of its own, so the import lands in the owner's account (Phase 17)."""
    now = time.time()
    for t in [t for t, v in _tokens.items() if v["expires"] < now]:
        del _tokens[t]
    token = secrets.token_urlsafe(16)
    _put(token, {"expires": now + TOKEN_TTL_S, "owner": owner, "portfolio_id": None})
    return token


def check_token(token: str | None) -> bool:
    t = _get(token or "")
    return bool(t) and t["expires"] >= time.time()


def complete_token(token: str, portfolio_id: str) -> None:
    if t := _get(token):
        _put(token, {**t, "portfolio_id": portfolio_id})


def token_owner(token: str) -> str | None:
    t = _get(token)
    return t["owner"] if t and t["expires"] >= time.time() else None


def token_result(token: str) -> str | None:
    t = _get(token)
    return t["portfolio_id"] if t else None
