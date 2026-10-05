# FinBERT scorer Lambda image (Phase 15): the backend image plus CPU-only torch, transformers and the model
# baked in at build time, so a cold start never downloads it (~440 MB) and the function needs no internet.
FROM public.ecr.aws/lambda/python:3.12
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY backend/pyproject.toml backend/uv.lock /tmp/build/
RUN cd /tmp/build && uv export --frozen --no-dev --no-hashes --format requirements-txt > requirements.txt \
    && uv pip install --system --no-cache -r requirements.txt --target "${LAMBDA_TASK_ROOT}" \
    && uv pip install --system --no-cache --target "${LAMBDA_TASK_ROOT}" \
       --index-url https://download.pytorch.org/whl/cpu torch \
    && uv pip install --system --no-cache --target "${LAMBDA_TASK_ROOT}" transformers \
    && rm -rf /tmp/build
ENV HF_HOME=/opt/hf PYTHONPATH=${LAMBDA_TASK_ROOT}
RUN python -c "from transformers import AutoModelForSequenceClassification as M, AutoTokenizer as T; \
M.from_pretrained('ProsusAI/finbert'); T.from_pretrained('ProsusAI/finbert')"
COPY backend/app ${LAMBDA_TASK_ROOT}/app
COPY config ${LAMBDA_TASK_ROOT}/config
ENV CONFIG_DIR=${LAMBDA_TASK_ROOT}/config DATA_DIR=/tmp/data STORAGE=s3 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
CMD ["app.aws.handlers.news_score"]
