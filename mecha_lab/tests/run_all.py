import os, sys, runpy, subprocess
HERE = os.path.dirname(os.path.abspath(__file__))
tests = sys.argv[1:] or sorted(f for f in os.listdir(HERE) if f.startswith('test_') and f.endswith('.py'))
failed = []
for t in tests:
    print('=' * 70, '\n', t)
    r = subprocess.run([sys.executable, os.path.join(HERE, t)], cwd=HERE)
    if r.returncode:
        failed.append(t)
print('\nFAILED FILES:', failed or 'none')
sys.exit(1 if failed else 0)
