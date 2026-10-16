"""API load test (Phase 18, NFR2: p95 < 1 s for read endpoints).

Each simulated user opens the dashboard the way the frontend does: list portfolios, then the overview,
risk, look-through, news and actions pages for one of them, with a short think time between pages.

Local (API on :8000, started with `uv run uvicorn app.main:app` from backend/):
  uvx locust -f scripts/loadtest/locustfile.py --host http://localhost:8000 \
      --headless -u 50 -r 5 -t 2m --csv docs/loadtest/local

Cloud (after deploy): use the CloudFront URL + /api and a Cognito access token (copy it from the
browser's developer tools → Application → Local storage once signed in):
  ACCESS_TOKEN=eyJ... uvx locust -f scripts/loadtest/locustfile.py --host https://xxxx.cloudfront.net/api \
      --headless -u 20 -r 2 -t 2m --csv docs/loadtest/cloud

--csv writes *_stats.csv with the 50/95/99th percentiles per endpoint for the report.
"""

import os
import random

from locust import HttpUser, between, task

TOKEN = os.environ.get("ACCESS_TOKEN")


class DashboardUser(HttpUser):
    wait_time = between(1, 3)  # seconds a person spends on a page

    def on_start(self):
        if TOKEN:
            self.client.headers["X-Access-Token"] = TOKEN  # what the frontend sends (see frontend/src/api.ts)
        r = self.client.get("/portfolio", name="/portfolio")
        ids = [p["portfolio_id"] for p in r.json()] if r.ok else []
        self.pid = random.choice(ids) if ids else None

    def page(self, suffix: str, weight_name: str):
        if self.pid:
            self.client.get(f"/portfolio/{self.pid}{suffix}", name=f"/portfolio/[id]{weight_name}")

    @task(5)
    def overview(self):
        self.page("", "")

    @task(3)
    def risk(self):
        self.page("/risk", "/risk")

    @task(3)
    def exposure(self):
        self.page("/exposure", "/exposure")

    @task(2)
    def news(self):
        self.page("/news", "/news")

    @task(2)
    def recommendations(self):
        self.page("/recommendations", "/recommendations")

    @task(1)
    def health(self):
        self.client.get("/health")
