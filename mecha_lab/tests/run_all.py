import os, sys, runpy, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
tests = sys.argv[1:] or sorted(f for f in os.listdir(HERE) if f.startswith('test_') and f.endswith('.py'))
failed = []
for t in tests:
    print('=' * 70, '\n', t)
    r = subprocess.run([sys.executable, os.path.join(HERE, t)], cwd=HERE, stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT, text=True, errors='replace')
    sys.stdout.write(r.stdout)
    sys.stdout.flush()
    # (a file that ends with summary() alone exits 0 with a failed check in it: its FAIL lines count too)
    if r.returncode or any(ln.startswith('FAIL ') for ln in r.stdout.splitlines()):
        failed.append(t)
print('\nFAILED FILES:', failed or 'none')
sys.exit(1 if failed else 0)
