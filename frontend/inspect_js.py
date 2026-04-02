import re
from pathlib import Path
p = Path('frontend/main.aac23269.js')
if not p.exists():
    print('missing file')
    raise SystemExit(0)
s = p.read_text(encoding='utf-8', errors='ignore')
for m in re.finditer(r'check-user', s):
    start=max(0,m.start()-260)
    end=min(len(s),m.end()+260)
    print('---')
    print(s[start:end])
