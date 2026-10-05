"""CAS import (FR2 extension): upload a CAS PDF, get a portfolio of every fund in it, then its risk rating.

A session token gates uploads. The laptop opens a session and shows a QR code of the phone URL carrying the
token, so a phone on the same Wi-Fi can upload straight from its email; the laptop polls for the result.
"""

import socket
from datetime import UTC, datetime
from typing import Annotated

import httpx
import segno
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.api.portfolio import Store, User, read_config
from app.aws.storage import persist
from app.config import get_settings
from app.models.portfolio import Holding, PortfolioCreate
from app.services import cas_import as cas

router = APIRouter(prefix="/import", tags=["import"])


def lan_ip() -> str:
    """This machine's address on the local network (no packet is sent); localhost when offline."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


@router.post("/session")
def open_session(
    port: Annotated[int, Query(ge=1, le=65535)] = 5173,
    origin: Annotated[str | None, Query(pattern=r"^https://[A-Za-z0-9.-]+$")] = None,
) -> dict:
    """origin: the page's own https origin (deployed); without it the QR uses this machine's LAN address."""
    token = cas.new_token()
    base = origin or f"http://{lan_ip()}:{port}"
    url = f"{base}/#/import/{token}"
    svg = segno.make(url, error="m").svg_inline(scale=5, dark="#1e2235", light="#ffffff", border=2)
    return {"token": token, "phone_url": url, "qr_svg": svg, "expires_in": cas.TOKEN_TTL_S}


@router.get("/session/{token}")
def session_status(token: str) -> dict:
    return {"valid": cas.check_token(token), "portfolio_id": cas.token_result(token)}


@router.post("", status_code=201)
async def import_cas(
    user: User,
    store: Store,
    file: Annotated[UploadFile, File(description="CAS PDF from CAMS, KFintech or MF Central")],
    password: Annotated[str, Form(max_length=64)],
    token: Annotated[str, Form(max_length=64)],
    name: Annotated[str, Form(max_length=100)] = "",
) -> dict:
    if not cas.check_token(token):
        raise HTTPException(
            403, "This import link has expired. Open Import again on your laptop for a fresh code."
        )
    data = await file.read(cas.MAX_PDF_BYTES + 1)
    try:
        parsed = cas.parse_cas(data, password)
        funds, skipped = cas.funds_from_cas(parsed)
        if not funds:
            raise cas.CASImportError("No mutual fund holdings with units were found in this statement.")
        universe_names = {
            str(f["scheme_code"]): f["name"] for f in read_config("universe.yaml")["mutual_funds"]
        }
        universe = set(universe_names)
        with httpx.Client(timeout=30) as client:
            registry = cas.register_funds(
                [f.scheme_code for f in funds if f.scheme_code not in universe],
                get_settings().data_dir,
                client,
            )
    except cas.CASImportError as e:
        raise HTTPException(422, str(e)) from e
    except httpx.HTTPError as e:
        raise HTTPException(
            502, "Couldn't fetch fund prices from mfapi.in; check the internet connection and try again."
        ) from e
    finally:
        del password  # never kept beyond the parse

    persist("processed/extra_funds.json")
    persist("processed/nav")
    holdings = [
        Holding(
            asset_type="MF",
            asset_id=f.scheme_code,
            quantity=round(f.units, 4),
            # cost basis per unit; when a statement prints no cost, today's value is used so P/L starts at 0
            avg_cost=round((f.cost if f.cost is not None else f.value) / f.units, 4),
        )
        for f in funds
    ]
    period = (parsed.get("statement_period") or {}).get("to", "")
    p = store.create(
        user,
        PortfolioCreate(
            name=name.strip() or f"Imported funds ({period or datetime.now(UTC).strftime('%d %b %Y')})",
            holdings=holdings,
        ),
    )
    cas.complete_token(token, p.portfolio_id)
    notes = []
    if any(f.cost is None for f in funds):
        notes.append("Some funds had no cost in the statement; their P/L starts from today’s value.")
    if parsed.get("parse_warnings"):
        notes.append(
            "The statement had rows the parser couldn’t reconcile; check unit counts against your statement."
        )
    return {
        "portfolio_id": p.portfolio_id,
        "statement_to": period,
        "funds": [
            {
                "scheme_code": f.scheme_code,
                "name": universe_names.get(f.scheme_code)
                or registry.get(f.scheme_code, {}).get("name")
                or f.name,
                "units": f.units,
                "value": f.value,
                "cost": f.cost,
                "in_universe": f.scheme_code in universe,
            }
            for f in sorted(funds, key=lambda f: -f.value)
        ],
        "skipped": skipped,
        "notes": notes,
    }
