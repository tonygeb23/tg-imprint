"""No em dashes or en dashes anywhere in the project. Tony's rule.

A screen reader either skips a dash or says the words "em dash", and neither
is what the sentence meant. This runs tools/nodashes.py in report mode over
the whole tree and fails if it finds one.

    python tests/test_nodashes.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

result = subprocess.run([sys.executable, os.path.join(HERE, "tools", "nodashes.py")],
                        capture_output=True, text=True, encoding="utf-8")
print(result.stdout.strip())
ok = result.returncode == 0
print("  ok   no dashes anywhere" if ok else "  FAIL dashes found, see above")
print("\n%d/1 checks passed" % (1 if ok else 0))
sys.exit(0 if ok else 1)
