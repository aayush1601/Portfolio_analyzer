"""FinBERT scoring (Phase 7). Needs the `ml` dependency group (torch + transformers); the API image skips it.

  uv run --group ml python -m app.services.sentiment score           # score news not yet scored
  uv run --group ml python -m app.services.sentiment sample 200      # export headlines to label by hand
  uv run --group ml python -m app.services.sentiment eval <csv>      # accuracy / macro-F1 vs your labels

Output: data/processed/sentiment.parquet, one row per news_id. Only new articles are scored, so a run after
each collection is cheap. The headline is scored (FinBERT was trained on single financial sentences).
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.analytics.sentiment import evaluate, to_scores
from app.config import get_settings
from app.services.news_pipeline import load_news

log = logging.getLogger(__name__)
MODEL = "ProsusAI/finbert"
BATCH = 16
MAX_TOKENS = 128  # headlines are short; caps cost on the odd run-on title


def score_texts(texts: list[str]) -> pd.DataFrame:
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL).eval()
    labels = [model.config.id2label[i] for i in range(model.config.num_labels)]
    chunks = []
    with torch.inference_mode():
        for i in range(0, len(texts), BATCH):
            batch = tok(
                texts[i : i + BATCH],
                padding=True,
                truncation=True,
                max_length=MAX_TOKENS,
                return_tensors="pt",
            )
            chunks.append(model(**batch).logits.softmax(dim=-1).numpy())
    return to_scores(np.concatenate(chunks) if chunks else np.empty((0, len(labels))), labels)


def sentiment_path(data_dir: Path) -> Path:
    return data_dir / "processed" / "sentiment.parquet"


def load_sentiment(data_dir: Path) -> pd.DataFrame:
    f = sentiment_path(data_dir)
    return pd.read_parquet(f) if f.exists() else pd.DataFrame(columns=["news_id"])


def score_new(data_dir: Path) -> int:
    news, done = load_news(data_dir), load_sentiment(data_dir)
    todo = news[~news["news_id"].isin(done["news_id"])]
    if todo.empty:
        return 0
    scored = score_texts(todo["headline"].tolist()).assign(news_id=todo["news_id"].to_numpy(), model=MODEL)
    pd.concat([done, scored], ignore_index=True).to_parquet(sentiment_path(data_dir), index=False)
    return len(scored)


def news_with_sentiment(data_dir: Path) -> pd.DataFrame:
    """Processed news joined to its FinBERT scores (inner join: unscored news is left out)."""
    return load_news(data_dir).merge(load_sentiment(data_dir), on="news_id")


def main() -> None:
    from app.utils.log import setup_logging

    settings = get_settings()
    setup_logging(settings.log_level)
    cmd, *args = sys.argv[1:] or ["score"]
    if cmd == "score":
        log.info("sentiment done", extra={"fields": {"scored": score_new(settings.data_dir)}})
    elif cmd == "sample":
        # Random sample, so the labels reflect what the pipeline really sees. Fill `label` with
        # positive / neutral / negative *before* looking at the model's output.
        n = int(args[0]) if args else 200
        out = settings.data_dir / "labelled" / "news_sample.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        news = load_news(settings.data_dir)
        news.sample(min(n, len(news)), random_state=0)[["news_id", "headline"]].assign(label="").to_csv(
            out, index=False
        )
        log.info("sample written", extra={"fields": {"path": str(out)}})
    elif cmd == "eval":
        gold = pd.read_csv(args[0]).dropna(subset=["label"])
        gold = gold[gold["label"].isin(["positive", "neutral", "negative"])]
        pred = score_texts(gold["headline"].tolist())["label"]
        print(json.dumps(evaluate(gold["label"].reset_index(drop=True), pred), indent=2))
    else:
        sys.exit(f"unknown command {cmd!r}; use score | sample [n] | eval <csv>")


if __name__ == "__main__":
    main()
