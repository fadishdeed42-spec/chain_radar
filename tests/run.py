"""Tiny test runner (no pytest needed): python3 tests/run.py"""
import sys, os, importlib, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
fails = n = 0
for mod in sorted(f[:-3] for f in os.listdir(os.path.dirname(os.path.abspath(__file__))) if f.startswith('test_') and f.endswith('.py')):
    m = importlib.import_module(mod)
    for name in sorted(x for x in dir(m) if x.startswith('test_')):
        n += 1
        try:
            getattr(m, name)(); print('PASS', mod, name)
        except Exception:
            fails += 1; print('FAIL', mod, name); traceback.print_exc()
print(f'\n{n - fails}/{n} passed'); sys.exit(1 if fails else 0)
