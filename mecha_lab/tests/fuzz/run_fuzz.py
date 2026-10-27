"""Random feature-combination crash test: N scenarios, each in its own Blender process.

    <python with bpy> run_fuzz.py [count=100] [steps=12] [parallel=3] [first seed=1]

A scenario whose process dies (a signal / non-zero code without DONE) is a CRASH, one that runs out of time a HANG;
Python errors inside steps are counted as ERRORs (the step failed, Blender lived).  Writes fuzz_report.md next to
this file with every crash / hang (seed + last step) - rerun one with: scenario.py <seed> <steps>.
"""
import collections
import os
import resource
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
args = [a for a in sys.argv[1:]]
count = int(args[0]) if len(args) > 0 else 100
steps = int(args[1]) if len(args) > 1 else 12
parallel = int(args[2]) if len(args) > 2 else 3
first = int(args[3]) if len(args) > 3 else 1
TIMEOUT = 600


def one(seed):
    t = time.time()
    try:
        p = subprocess.run([sys.executable, os.path.join(HERE, 'scenario.py'), str(seed), str(steps)],
                           capture_output=True, text=True, timeout=TIMEOUT)
        out, code = p.stdout + p.stderr, p.returncode
    except subprocess.TimeoutExpired as ex:
        out = (ex.stdout or b'').decode('utf-8', 'replace') if isinstance(ex.stdout, bytes) else (ex.stdout or '')
        return seed, 'HANG', out, time.time() - t
    status = 'OK' if code == 0 and 'DONE' in out else 'CRASH'
    return seed, status, out, time.time() - t


results = []
t0 = time.time()
with ThreadPoolExecutor(parallel) as ex:
    for seed, status, out, dt in ex.map(one, range(first, first + count)):
        lines = out.splitlines()
        steps_ = [l for l in lines if l.startswith('STEP')]
        errors = [l for l in lines if l.startswith(('ERROR', 'BAD'))]
        results.append((seed, status, steps_[-1] if steps_ else '', errors, dt, lines))
        print(f'{seed:4d} {status:5s} {dt:6.1f}s errors {len(errors)}  last: {steps_[-1] if steps_ else "-"}', flush=True)
peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
by = collections.Counter(r[1] for r in results)
err_kinds = collections.Counter(e.split(':')[0].split(' ', 2)[-1] + ': ' + e.split(':', 2)[-1].strip()[:90]
                                for r in results for e in r[3])
with open(os.path.join(HERE, 'fuzz_report.md'), 'w', encoding='utf-8') as f:
    f.write(f'# Fuzz report: {count} scenarios x {steps} steps (seeds {first}..{first + count - 1})\n\n')
    f.write(f'{dict(by)} in {time.time() - t0:.0f} s, largest Blender process {peak:.0f} MB\n\n')
    for seed, status, last, errors, dt, lines in results:
        if status != 'OK':
            f.write(f'## seed {seed}: {status} ({dt:.0f} s)\n\nlast step: `{last}`\n\n```\n' +
                    '\n'.join(lines[-25:]) + '\n```\n\n')
    f.write('## Python errors inside steps (Blender lived)\n\n')
    for k, n in err_kinds.most_common():
        f.write(f'- {n} x {k}\n')
print(dict(by), f'{time.time() - t0:.0f}s', f'peak {peak:.0f} MB')
print('errors:', err_kinds.most_common(20))
