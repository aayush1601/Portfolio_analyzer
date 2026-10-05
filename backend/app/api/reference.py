"""Reference data for the UI: universe names (holdings editor) and the caps the charts draw."""

from fastapi import APIRouter

from app.api.portfolio import read_config
from app.config import get_settings
from app.services.cas_import import load_registry

router = APIRouter(tags=["reference"])


@router.get("/reference")
def reference() -> dict:
    u = read_config("universe.yaml")
    return {
        "stocks": [{"symbol": s["symbol"], "name": s["name"], "sector": s["sector"]} for s in u["stocks"]],
        "funds": [
            {
                "scheme_code": str(f["scheme_code"]),
                "name": f["name"],
                "amc": f["amc"],
                "category": f["category"],
            }
            for f in u["mutual_funds"]
        ]
        # funds registered by a CAS import: valued and risk-rated, outside the research universe
        + [{**f, "in_universe": False} for f in load_registry(get_settings().data_dir).values()],
        "caps": read_config("recommendations.yaml")["caps"],
    }
