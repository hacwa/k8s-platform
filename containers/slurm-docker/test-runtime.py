#!/usr/bin/env python3
"""Integration tests run as UID 401 against the worker's real nested daemon."""
import json
import os
from pathlib import Path
import signal
import subprocess
import time

IMAGE = 'alpine:3.23.4@sha256:5b10f432ef3da1b8d4c7eb6c487f2f5a8f096bc91145e68878dd4a5019afde11'
ENV = {**os.environ, 'SLURM_JOB_ID': '1234', 'SLURM_CPUS_PER_TASK': '1',
       'SLURM_MEM_PER_NODE': '256'}
LABEL = 'hacwa.slurm.job-id=1234'


def docker(*args):
    return subprocess.check_output(['docker', *args], text=True).strip()


def containers():
    return docker('ps', '-aq', '--filter', f'label={LABEL}').split()


def run(*args, **kwargs):
    return subprocess.run(['slurm-docker-run', IMAGE, *args], env=ENV,
                          text=True, capture_output=True, timeout=60, **kwargs)


assert os.getuid() == 401, 'Test the real Slurm service user'
missing = subprocess.run(['slurm-docker-run', IMAGE, 'true'],
                         env={k: v for k, v in ENV.items() if k != 'SLURM_JOB_ID'},
                         text=True, capture_output=True, timeout=10)
assert missing.returncode != 0 and 'Slurm allocation' in missing.stderr, missing
oversized = subprocess.run(['slurm-docker-run', IMAGE, 'true'],
                           env={**ENV, 'SLURM_MEM_PER_NODE': '4096'},
                           text=True, capture_output=True, timeout=10)
assert oversized.returncode != 0 and 'exceeds' in oversized.stderr, oversized
result = run('sh', '-ec', '''
    test "$(id -u)" = 401
    test "$(cat /sys/fs/cgroup/memory.max)" = 268435456
    test "$(cat /sys/fs/cgroup/cpu.max)" = '100000 100000'
    touch /srv/slurm-media/docker-test
    if touch /mnt/plex_tv/must-not-write 2>/dev/null; then exit 1; fi
    echo 'Hello world from Docker on Slurm'
''')
assert result.returncode == 0 and 'Hello world' in result.stdout, result
assert not containers(), 'Successful jobs must not leave containers'
assert run('sh', '-c', 'exit 42').returncode == 42, 'Preserve application exit codes'
assert not containers(), 'Failed jobs must not leave containers'

for cancellation in (signal.SIGTERM, signal.SIGKILL):
    job = subprocess.Popen(['slurm-docker-run', IMAGE, 'sleep', '300'],
                           env=ENV, start_new_session=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for attempt in range(100):
            ids = containers()
            if ids:
                state = json.loads(docker('inspect', ids[0]))[0]
                if state['State']['Running']:
                    break
            time.sleep(.1)
        else:
            raise AssertionError('Background job never started')
        config = state['HostConfig']
        assert config['Memory'] == 268435456 and config['MemorySwap'] == 268435456
        assert config['NanoCpus'] == 1000000000 and config['CpusetCpus']
        assert config['NetworkMode'] == 'host' and not config['Privileged']
        assert config['PidsLimit'] == 256
        actual_cgroup = Path('/proc', str(state['State']['Pid']), 'cgroup').read_text()
        parent = json.loads(Path('/run/slurm-docker/daemon.json').read_text())['cgroup-parent']
        assert actual_cgroup.strip().startswith('0::' + parent + '/'), actual_cgroup
        os.killpg(job.pid, cancellation)
        job.wait(timeout=15)
        if cancellation == signal.SIGKILL:
            # Slurm's root epilog also removes containers after an uncatchable kill.
            subprocess.run(['slurm-docker-cleanup'], env=ENV, check=True, timeout=15)
        assert not containers(), f'Container survived {cancellation}'
    finally:
        if job.poll() is None:
            os.killpg(job.pid, signal.SIGKILL)
            job.wait(timeout=10)
        subprocess.run(['slurm-docker-cleanup'], env=ENV, check=True, timeout=15)
print('PASS: UID, mounts, CPU/memory limits, exit status, SIGTERM and SIGKILL cleanup')
