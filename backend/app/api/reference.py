"""Reference data for the UI: universe names (holdings editor) and the caps the charts draw."""

from fastapi import APIRouter

from app.api.portfolio import read_config

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
        ],
        "caps": read_config("recommendations.yaml")["caps"],
    }
