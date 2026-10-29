#!/usr/bin/env bash
set -euo pipefail
image="${1:?Pass the built worker image}"
name="slurm-docker-test-${GITHUB_RUN_ID:-local}"
cleanup() {
  status=$?
  if (( status != 0 )); then docker logs "$name" || true; fi
  docker rm --force "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
# Match the existing Kubernetes worker's privilege, cgroup v2 and resource budget.
docker run --detach --name "$name" --privileged --cgroupns=host \
  --cpus=1 --memory=2g --memory-swap=2g \
  --tmpfs /var/lib/docker:rw,size=1g \
  --entrypoint /bin/bash "$image" -ec '
    mkdir -p /srv/slurm-media /mnt/plex_tv
    chown 401:401 /srv/slurm-media
    chmod 0555 /mnt/plex_tv
    python3 -c '\''import runpy; runpy.run_path("/usr/local/libexec/slurm-docker-runtime.py")["prepare"]()'\''
    exec dockerd --config-file=/run/slurm-docker/daemon.json
  '
ready=no
for attempt in $(seq 1 60); do
  if docker exec --user 401:401 "$name" docker info >/dev/null 2>&1; then
    ready=yes; break
  fi
  sleep 1
done
[[ $ready == yes ]]
docker cp containers/slurm-docker/test-runtime.py "$name:/tmp/test-runtime.py"
docker exec --user 401:401 "$name" python3 /tmp/test-runtime.py
