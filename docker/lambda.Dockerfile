# Backend Lambda image (Phase 14/15): the FastAPI app (API Gateway) and the pipeline jobs.
# One image; Terraform picks the handler per function via image_config.command.
FROM public.ecr.aws/lambda/python:3.12
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY backend/pyproject.toml backend/uv.lock /tmp/build/
RUN cd /tmp/build && uv export --frozen --no-dev --no-hashes --format requirements-txt > requirements.txt \
    && uv pip install --system --no-cache -r requirements.txt --target "${LAMBDA_TASK_ROOT}" \
    && rm -rf /tmp/build
COPY backend/app ${LAMBDA_TASK_ROOT}/app
COPY config ${LAMBDA_TASK_ROOT}/config
# Lambda runs as a non-root user: files copied with owner-only permissions (e.g. 600 on a laptop) would fail
# to import with PermissionError, so make the code and config world-readable whatever the checkout's modes.
RUN chmod -R a+rX ${LAMBDA_TASK_ROOT}/app ${LAMBDA_TASK_ROOT}/config
ENV CONFIG_DIR=${LAMBDA_TASK_ROOT}/config DATA_DIR=/tmp/data STORAGE=s3
CMD ["app.aws.handlers.api"]
