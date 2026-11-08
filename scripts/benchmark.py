"""Evaluate OCR predictions against manually verified ground truth JSONL.

Usage: python scripts/benchmark.py labeled.jsonl
JSONL: {"image": "path/to/image.png", "reference": "...", "language": "my", "mode": "accurate"}
"""
import json
import sys
import unicodedata
from pathlib import Path

if __name__ == '__main__' and __package__ in (None, ''):
    # Allow execution as `python scripts/benchmark.py ...` from any directory.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ocr import recognize_local
from app.preprocess import load_image


def normalized(s):
    return unicodedata.normalize('NFC', s).replace('\r\n','\n').strip()


def edit_distance(a, b):
    prev=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        now=[i]+[0]*len(b)
        for j,y in enumerate(b,1):
            now[j]=min(now[j-1]+1,prev[j]+1,prev[j-1]+(x!=y))
        prev=now
    return prev[-1]


def report(rows):
    total=0; dist=0; exact=0
    for row in rows:
        ref=normalized(row['reference'])
        if not ref: continue
        img=load_image(Path(row['image']).read_bytes())
        actual=normalized(recognize_local(img,row.get('language','my'),row.get('mode','accurate'))['text'])
        d=edit_distance(ref,actual)
        total+=len(ref); dist+=d; exact+=(ref==actual)
        print(f"{row['image']} CER={d/len(ref)*100:.1f}% exact={ref==actual}")
    if not total: raise SystemExit('No nonempty ground truth rows.')
    print(f'Combined CER={dist/total*100:.2f}% | {exact} exact matches')
    return dist/total


if __name__=='__main__':
    if len(sys.argv)<2: raise SystemExit(__doc__)
    with open(sys.argv[1],encoding='utf-8') as handle:
        report([json.loads(x) for x in handle if x.strip()])
