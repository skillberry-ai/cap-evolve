FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install cap-evolve core (zero runtime deps — pure stdlib)
COPY core/ /app/core/
RUN pip install --no-cache-dir /app/core

# Install tau2-bench and litellm for benchmark evaluation
RUN git clone --depth 1 https://github.com/sierra-research/tau2-bench.git /app/tau2-bench && \
    pip install --no-cache-dir /app/tau2-bench litellm

# Copy skills library
COPY skills/ /app/skills/

# Project config (.capevolve/project/) is generated at runtime by the
# intake/scaffold phase and must be mounted or copied into the container
# at launch time. See the runner Job manifest for an example.

ENV PYTHONPATH="/app" \
    CAPEVOLVE_SKILLS_DIR="/app/skills" \
    TAU2_DATA_DIR="/app/tau2-bench/data" \
    GIT_EDITOR=true \
    HOME=/tmp

CMD ["sleep", "infinity"]
