FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build libopenmpi-dev openmpi-bin git \
    python3 python3-matplotlib python3-reportlab poppler-utils \
    && rm -rf /var/lib/apt/lists/*
ENV OMPI_ALLOW_RUN_AS_ROOT=1 OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
    OMP_DYNAMIC=FALSE MPLCONFIGDIR=/tmp/matplotlib
WORKDIR /work
