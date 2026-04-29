FROM myoung34/github-runner:ubuntu-jammy

# Pre-install Python 3.11 — base image runs as root (RUN_AS_ROOT=true by default)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       python3.11 \
       python3.11-venv \
       python3-pip \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/pip pip /usr/bin/pip3 1 \
    && rm -rf /var/lib/apt/lists/*
