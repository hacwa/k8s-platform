# syntax=docker/dockerfile:1
FROM docker:29.9.2-dind AS docker-engine
FROM ghcr.io/slinkyproject/slurmd:26.05-ubuntu26.04@sha256:dc415d580e0c9d9b2e8c785bfe90f2541670bc9a5de255fba9117032eb247d10
LABEL org.opencontainers.image.source="https://github.com/hacwa/k8s-platform"
USER root
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ARG NVIDIA_TOOLKIT_VERSION=1.20.1-1
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg python3 iptables iproute2 xz-utils \
    && curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
      | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
    && curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
      > /etc/apt/sources.list.d/nvidia-container-toolkit.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      nvidia-container-toolkit=${NVIDIA_TOOLKIT_VERSION} \
      nvidia-container-toolkit-base=${NVIDIA_TOOLKIT_VERSION} \
      libnvidia-container-tools=${NVIDIA_TOOLKIT_VERSION} \
      libnvidia-container1=${NVIDIA_TOOLKIT_VERSION} \
    && rm -rf /var/lib/apt/lists/*
COPY --from=docker-engine /usr/local/bin/ /usr/local/bin/
COPY runtime.py /usr/local/libexec/slurm-docker-runtime.py
RUN chmod 0755 /usr/local/libexec/slurm-docker-runtime.py \
    && ln -s /usr/local/libexec/slurm-docker-runtime.py /usr/local/bin/slurm-docker-run \
    && ln -s /usr/local/libexec/slurm-docker-runtime.py /usr/local/bin/slurm-docker-cleanup \
    && ln -s /usr/local/libexec/slurm-docker-runtime.py /usr/local/bin/slurm-docker-entrypoint \
    && nvidia-ctk config --in-place --set nvidia-container-cli.load-kmods=false \
    && nvidia-ctk config --in-place --set nvidia-container-runtime.mode=legacy
RUN <<'SUPERVISOR'
cat > /etc/supervisor/conf.d/dockerd.conf <<'CONFIG'
[program:dockerd]
command=/usr/local/bin/dockerd --config-file=/run/slurm-docker/daemon.json
priority=5
autostart=true
autorestart=true
startsecs=2
stopwaitsecs=30
stdout_logfile=/dev/stdout
stdout_logfile_maxbytes=0
stderr_logfile=/dev/stderr
stderr_logfile_maxbytes=0
CONFIG
SUPERVISOR
ENV DOCKER_HOST=unix:///run/slurm-docker/docker.sock
ENTRYPOINT ["/usr/local/bin/slurm-docker-entrypoint"]
