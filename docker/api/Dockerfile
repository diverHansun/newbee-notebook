ARG BASE_IMAGE=python:3.11-slim
ARG DOCKER_CLI_IMAGE=docker:29-cli
FROM ${DOCKER_CLI_IMAGE} AS docker-cli
FROM ${BASE_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

ARG TORCH_INSTALL_MODE=cpu
ARG TORCH_VERSION=2.9.0
ARG TORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN grep -Ev '^torch([[:space:]]|[<>=!~]|$)' requirements.txt > /tmp/requirements.txt && \
    if [ "$TORCH_INSTALL_MODE" = "cpu" ]; then \
        python -m pip install --no-cache-dir --index-url "$TORCH_CPU_INDEX_URL" "torch==${TORCH_VERSION}"; \
    elif [ "$TORCH_INSTALL_MODE" = "pypi" ]; then \
        python -m pip install --no-cache-dir "torch==${TORCH_VERSION}"; \
    elif [ "$TORCH_INSTALL_MODE" != "skip" ]; then \
        echo "Unsupported TORCH_INSTALL_MODE: $TORCH_INSTALL_MODE" >&2; \
        exit 1; \
    fi && \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm -f /tmp/requirements.txt

# Token counting is local text processing, not model inference. Cache its
# vocabulary at build time so a fresh container never downloads it on chat.
ENV TIKTOKEN_CACHE_DIR=/opt/tiktoken-cache
RUN python -c "import tiktoken; tiktoken.get_encoding('cl100k_base')"

# Only the optional monitor image needs Flower; keep API/worker dependencies intact.
ARG INSTALL_FLOWER=false
RUN if [ "$INSTALL_FLOWER" = "true" ]; then python -m pip install --no-cache-dir "flower==2.0.1"; fi

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker

COPY . .

EXPOSE 8000

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8000"]
