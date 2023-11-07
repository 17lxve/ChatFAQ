FROM modelw/base:2023.04

COPY --chown=user pyproject.toml poetry.lock README.md ./

RUN modelw-docker install \
    && modelw-docker run poetry run playwright install firefox

# Install GPU pytorch
ARG TORCH_GPU_URL=https://download.pytorch.org/whl/cu121/torch-2.1.0%2Bcu121-cp310-cp310-linux_x86_64.whl
RUN modelw-docker run poetry add ${TORCH_GPU_URL}

COPY --chown=user . .

RUN modelw-docker build

CMD ["bash", "-c", "modelw-docker run python -m daphne -b 0.0.0.0 -p 8000 back.config.asgi:application"]
