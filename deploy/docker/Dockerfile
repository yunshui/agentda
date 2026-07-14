FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY deploy/requirements.in .
RUN pip install --no-cache-dir -r requirements.in -i https://pypi.tuna.tsinghua.edu.cn/simple

FROM python:3.12-slim

WORKDIR /data/apps

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY agent-core/ agent-core/
COPY api-core/ api-core/
COPY mcp-core/ mcp-core/
COPY tools/ tools/
COPY logging_lib.py .

COPY deploy/docker/entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000 8001 8002

CMD ["./entrypoint.sh"]
