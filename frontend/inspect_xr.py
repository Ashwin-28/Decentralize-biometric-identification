import re
from pathlib import Path
s = Path('frontend/main.aac23269.js').read_text(encoding='utf-8', errors='ignore')
for m in re.finditer(r'xr=', s):
    st=max(0,m.start()-120)
    en=min(len(s),m.start()+220)
    chunk=s[st:en]
    if 'kindstone' in chunk or '/api' in chunk:
        print('---')
        print(chunk)
