"""Backtest routes (FR9): start a run in the background, list runs, read results (docs/api/openapi.yaml)."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Path
from pydantic import BaseModel, Field

from app.aws.storage import persist
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
        persist(f"backtests/{run_id}")
    except Exception as e:  # surfaced through the run's status instead of being lost in a background thread
        f = svc.run_dir(get_settings().data_dir, run_id) / "results.json"
        f.write_text(svc.json.dumps({"run_id": run_id, "status": "FAILED", "error": str(e)}))
        persist(f"backtests/{run_id}")
        raise


def _invoke(function: str, payload: dict) -> None:
    """Fire-and-forget: the backtest Lambda runs the job and persists its results to S3."""
    import boto3

    boto3.client("lambda").invoke(
        FunctionName=function, InvocationType="Event", Payload=svc.json.dumps(payload)
    )


@router.post("", status_code=202)
def start(body: BacktestRequest, background: BackgroundTasks) -> dict:
    overrides = {
        k: (str(v) if isinstance(v, date) else v) for k, v in body.model_dump().items() if v is not None
    }
    run_id = datetime.now(UTC).strftime("bt_%Y%m%d_%H%M%S")
    run_dir = svc.run_dir(get_settings().data_dir, run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results.json").write_text(svc.json.dumps({"run_id": run_id, "status": "QUEUED"}))
    s = get_settings()
    if s.storage == "s3":
        # Lambda freezes after the response, so in-process background work never finishes, and a run
        # (~1 min) outlasts API Gateway's 30 s limit. Record QUEUED where every container sees it, then
        # hand the run to the backtest Lambda; the page polls the run list until it is DONE.
        persist(f"backtests/{run_id}")
        if s.backtest_function:
            _invoke(s.backtest_function, {"run_id": run_id, "overrides": overrides})
            return {"run_id": run_id, "status": "QUEUED"}
        _run(run_id, overrides)  # no worker configured: inline, may time out on long runs
        return {"run_id": run_id, "status": "DONE"}
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
