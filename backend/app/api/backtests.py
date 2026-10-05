"""Backtest routes (FR9): start a run in the background, list runs, read results (docs/api/openapi.yaml)."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path
from pydantic import BaseModel, Field

from app.config import get_settings
from app.services import backtest as svc

router = APIRouter(prefix="/backtest", tags=["backtest"])
RunId = Annotated[str, Path(pattern=r"^bt_\d{8}_\d{6}$")]


class BacktestRequest(BaseModel):
    start: date | None = None
    end: date | None = None
    cost_bps: float | None = Field(default=None, ge=0, le=200)


def _run(run_id: str, overrides: dict) -> None:
    try:
        svc.run(overrides, run_id)
    except Exception as e:  # surfaced through the run's status instead of being lost in a background thread
        f = svc.run_dir(get_settings().data_dir, run_id) / "results.json"
        f.write_text(svc.json.dumps({"run_id": run_id, "status": "FAILED", "error": str(e)}))
        raise


@router.post("", status_code=202)
def start(body: BacktestRequest, background: BackgroundTasks) -> dict:
    overrides = {
        k: (str(v) if isinstance(v, date) else v) for k, v in body.model_dump().items() if v is not None
    }
    run_id = datetime.now(UTC).strftime("bt_%Y%m%d_%H%M%S")
    run_dir = svc.run_dir(get_settings().data_dir, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results.json").write_text(svc.json.dumps({"run_id": run_id, "status": "QUEUED"}))
    background.add_task(_run, run_id, overrides)
    return {"run_id": run_id, "status": "QUEUED"}


@router.get("")
def runs() -> list[dict]:
    return svc.list_runs(get_settings().data_dir)


@router.get("/{run_id}")
def result(run_id: RunId) -> dict:
    r = svc.load_run(get_settings().data_dir, run_id)
    if r is None:
        raise HTTPException(404, "backtest run not found")
    return r
