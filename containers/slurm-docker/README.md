# Slurm Docker worker

Extends the pinned Slinky Slurm worker with a pinned Docker engine and NVIDIA
Container Toolkit. The existing upstream entrypoint still starts Slurm and its
supervised services; supervisord also starts a worker-local Docker daemon.
There is no host Docker socket mount or TCP Docker API.

`slurm-docker-run IMAGE [COMMAND [ARG...]]` runs one foreground container inside
an existing, single-node Slurm allocation. It preserves the submitting UID/GID,
limits CPU and memory to the allocation, inherits the Slurm task CPU affinity,
and passes allocated GPU device IDs to the NVIDIA runtime. Supply a positive
`--mem` or `--mem-per-cpu` request. The existing workers have one CPU and 2 GiB
including Slurm and Docker overhead; leave memory headroom for both daemons.

The workspace `/srv/slurm-media` is mounted read/write and the source
`/mnt/plex_tv` read-only. Other host paths and arbitrary Docker flags are not
accepted by the helper. Job containers use the worker pod network, drop Linux
capabilities and enable no-new-privileges. Container output goes to the Slurm
batch log and application exit status is returned to Slurm. Normal exit and
catchable termination remove the container; the Slurm epilog removes any
remaining job-labelled containers after cancellation or an uncatchable kill.

The daemon creates job cgroups under the existing bounded worker cgroup.
Startup fails if finite worker CPU/memory limits or delegated cgroup v2
controllers cannot be established. Slurm schedules and records the batch job,
but Docker daemon children are outside the Slurm task cgroup, so Slurm process
accounting does not measure their complete CPU/memory usage. Explicit container
limits and the enclosing worker limits enforce the budget. This helper is for
the existing trusted, single-user pilot: access to a rootful Docker socket is
root-equivalent inside the privileged worker. It is not a multi-user security
boundary. Direct Docker API users can bypass the helper's options.

Docker images and writable container layers use disposable worker-local
`/var/lib/docker` storage; persistent job output belongs in the workspace.
GPU access retains the existing shared physical GPU and VRAM arrangement.
Apptainer and an interactive login node are outside this change.

The `Slurm Docker worker` workflow builds the image and runs real nested Docker
integration checks as UID 401, including limits, mounts, exit codes and both
SIGTERM and SIGKILL cleanup. Only a passing build on `main` is published to
GHCR. The deployment must pin the resulting digest after publication. No AWS
secrets or registry credentials need to be added for public image pulls.
