"""Pipeline events on the custom EventBridge bus (Phase 15). No-op when no bus is configured (local runs)."""

import json

from app.config import get_settings

SOURCE = "portfolio-intelligence"


def emit(detail_type: str, detail: dict) -> None:
    bus = get_settings().event_bus
    if not bus:
        return
    import boto3

    boto3.client("events").put_events(
        Entries=[
            {"Source": SOURCE, "DetailType": detail_type, "Detail": json.dumps(detail), "EventBusName": bus}
        ]
    )
