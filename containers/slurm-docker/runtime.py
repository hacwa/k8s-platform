#!/usr/bin/env python3
"""Worker-local Docker runtime and allocation-aware, foreground Slurm job runner."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time
import uuid

RUNTIME = Path('/run/slurm-docker')
SOCKET = 'unix:///run/slurm-docker/docker.sock'
WORKSPACE = '/srv/slurm-media'
SOURCE = '/mnt/plex_tv'
LABEL = 'hacwa.slurm.job-id'


def docker(*args, capture=False, check=True):
    env = os.environ.copy()
    for key in ('DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH'):
        env.pop(key, None)
    env['DOCKER_HOST'] = SOCKET
    return subprocess.run(['docker', '--host', SOCKET, *args], env=env,
                          text=True, capture_output=capture, check=check)


def positive(value, name):
    if not re.fullmatch(r'[1-9][0-9]*', str(value)):
        raise ValueError(f'{name} must be a positive integer')
    return int(value)


def current_cgroup():
    lines = Path('/proc/self/cgroup').read_text().splitlines()
    paths = [line[3:] for line in lines if line.startswith('0::')]
    if len(paths) != 1:
        raise RuntimeError('This runtime requires cgroup v2')
    relative = paths[0]
    base = Path('/sys/fs/cgroup')
    full = base / relative.lstrip('/')
    # A private cgroup mount may already be rooted at this container.
    if not full.is_dir():
        full = base
        relative = '/'
    if str(os.getpid()) not in (full / 'cgroup.procs').read_text().split():
        raise RuntimeError('Cannot identify this worker container cgroup safely')
    return full, relative


def prepare():
    if os.geteuid() != 0:
        raise RuntimeError('The Slurm worker entrypoint must run as root')
    cg, relative = current_cgroup()
    cpu_quota, cpu_period = (cg / 'cpu.max').read_text().split()
    memory = (cg / 'memory.max').read_text().strip()
    if cpu_quota == 'max' or memory == 'max':
        raise RuntimeError('Refusing to start Docker without worker CPU and memory limits')
    bounds = {'cpus': int(cpu_quota) / int(cpu_period), 'memory': int(memory)}
    RUNTIME.mkdir(mode=0o750, exist_ok=True)
    os.chown(RUNTIME, 0, 401)
    (RUNTIME / 'bounds.json').write_text(json.dumps(bounds))
    # Enable child cgroups only within the identified, bounded worker cgroup.
    available = set((cg / 'cgroup.controllers').read_text().split())
    enabled = set((cg / 'cgroup.subtree_control').read_text().split())
    required = {'cpu', 'memory', 'pids'}
    if not required <= available | enabled:
        raise RuntimeError('Worker cgroup does not delegate CPU, memory and PID controllers')
    missing = (required | ({'cpuset'} & available)) - enabled
    if missing:
        init = cg / 'slurm-runtime'
        init.mkdir(exist_ok=True)
        for _ in range(5):
            pids = (cg / 'cgroup.procs').read_text().split()
            if not pids:
                break
            if any(pid == '0' or not Path('/proc', pid).exists() for pid in pids):
                raise RuntimeError('Refusing to move processes outside this worker PID namespace')
            for pid in pids:
                try:
                    (init / 'cgroup.procs').write_text(pid)
                except ProcessLookupError:
                    pass
        (cg / 'cgroup.subtree_control').write_text(' '.join('+' + c for c in sorted(missing)))
    parent = relative.rstrip('/') + '/docker-jobs'
    config = {
        'hosts': [SOCKET], 'group': '401', 'data-root': '/var/lib/docker',
        'exec-root': '/run/slurm-docker/exec', 'pidfile': '/run/slurm-docker/dockerd.pid',
        'exec-opts': ['native.cgroupdriver=cgroupfs'], 'cgroup-parent': parent,
        'storage-driver': 'overlay2', 'bridge': 'none', 'iptables': False,
        'ip6tables': False, 'ip-forward': False, 'ip-masq': False,
        'userland-proxy': False, 'default-cgroupns-mode': 'private',
        'log-driver': 'local', 'log-opts': {'max-size': '10m', 'max-file': '2'},
        'runtimes': {'nvidia': {'path': '/usr/bin/nvidia-container-runtime', 'runtimeArgs': []}},
        # Keep the classic graph driver rather than nested containerd snapshotters.
        'features': {'containerd-snapshotter': False},
    }
    (RUNTIME / 'daemon.json').write_text(json.dumps(config, indent=2))
    for stale in (RUNTIME / 'dockerd.pid',):
        stale.unlink(missing_ok=True)


def wait_ready():
    for _ in range(60):
        if docker('info', capture=True, check=False).returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError('Worker Docker daemon did not become ready within 60 seconds')


def job_id():
    value = os.environ.get('SLURM_JOB_ID', '')
    if not re.fullmatch(r'[0-9]+', value):
        raise ValueError('Run this command inside a Slurm allocation')
    return value


def allocation():
    cpus = positive(os.environ.get('SLURM_CPUS_PER_TASK') or
                    os.environ.get('SLURM_CPUS_ON_NODE', ''), 'Slurm CPU allocation')
    if os.environ.get('SLURM_MEM_PER_NODE'):
        memory = positive(os.environ['SLURM_MEM_PER_NODE'], '--mem allocation')
    else:
        memory = positive(os.environ.get('SLURM_MEM_PER_CPU', ''), '--mem-per-cpu allocation') * cpus
    bounds = json.loads((RUNTIME / 'bounds.json').read_text())
    if cpus > bounds['cpus'] or memory * 1048576 > bounds['memory']:
        raise ValueError('Slurm request exceeds this Kubernetes worker allocation')
    gpu = os.environ.get('SLURM_STEP_GPUS') or os.environ.get('SLURM_JOB_GPUS')
    if gpu and not re.fullmatch(r'(?:[0-9]+|GPU-[a-zA-Z0-9-]+)(?:,(?:[0-9]+|GPU-[a-zA-Z0-9-]+))*', gpu):
        raise ValueError('Unsupported Slurm GPU device list')
    return cpus, memory, gpu


def run_job(args):
    jid = job_id()
    if not args or args[0].startswith('-') or any(c.isspace() for c in args[0]):
        raise ValueError('Usage: slurm-docker-run IMAGE [COMMAND [ARG...]]')
    cpus, memory, gpu = allocation()
    wait_ready()
    name = f'slurm-{jid}-{os.getpid()}-{uuid.uuid4().hex[:8]}'
    options = [
        'create', '--name', name, '--label', f'{LABEL}={jid}', '--pull=never',
        '--user', f'{os.getuid()}:{os.getgid()}', '--network=host', '--init',
        '--cpus', str(cpus), '--cpuset-cpus', ','.join(map(str, sorted(os.sched_getaffinity(0)))),
        '--memory', f'{memory}m', '--memory-swap', f'{memory}m', '--pids-limit', '256',
        '--cap-drop=ALL', '--security-opt=no-new-privileges=true',
        '--env', f'SLURM_JOB_ID={jid}', '--workdir', WORKSPACE,
        '--mount', f'type=bind,src={WORKSPACE},dst={WORKSPACE}',
        '--mount', f'type=bind,src={SOURCE},dst={SOURCE},readonly',
    ]
    if gpu:
        options += ['--runtime=nvidia', '--gpus', f'device={gpu}',
                    '--env', 'NVIDIA_DRIVER_CAPABILITIES=compute,utility,video']
    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)
    old = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)}
    try:
        if docker('image', 'inspect', args[0], capture=True, check=False).returncode:
            docker('pull', args[0])
        docker(*options, *args, capture=True)
        attached = docker('start', '--attach', name, check=False)
        state = docker('inspect', '--format', '{{.State.ExitCode}}', name, capture=True)
        code = int(state.stdout.strip())
        return code if code else attached.returncode
    finally:
        docker('rm', '--force', name, capture=True, check=False)
        for sig, handler in old.items():
            signal.signal(sig, handler)


def cleanup():
    jid = job_id()
    found = docker('ps', '--all', '--quiet', '--filter', f'label={LABEL}={jid}', capture=True)
    ids = found.stdout.split()
    if ids:
        docker('rm', '--force', *ids, capture=True)


def main():
    executable = Path(sys.argv[0]).name
    if executable == 'slurm-docker-entrypoint':
        prepare()
        os.execv('/usr/local/bin/entrypoint.sh', ['/usr/local/bin/entrypoint.sh', *sys.argv[1:]])
    if executable == 'slurm-docker-cleanup':
        cleanup()
        return 0
    if executable == 'slurm-docker-run':
        return run_job(sys.argv[1:])
    raise ValueError('Use one of the installed slurm-docker commands')


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        print(f'slurm-docker: {exc}', file=sys.stderr)
        sys.exit(1)
