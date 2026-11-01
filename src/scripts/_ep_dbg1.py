# -*- coding: utf-8 -*-
"""调试:检查 footer 边界假设是否成立,以及行级分类可行性。"""
import json, re, sys, os
sys.stdout.reconfigure(encoding='utf-8')

FOOT = re.compile(r'(关注公主号|关注公众号|epsilon-delta\s*数学|扫码了解更多课程|题型方法梳理班》讲义|小红书)')
PAGENUM = re.compile(r'^\s*[-—·]?\s*\d{1,4}\s*[-—·]?\s*$')

def load(p):
    return [json.loads(l) for l in open(p, encoding='utf-8')]

def footer_idx(blocks):
    idx = -1
    for i, b in enumerate(blocks):
        t = b.get('text') or ''
        if FOOT.search(t) or PAGENUM.match(t.strip()) and len(t.strip()) <= 4:
            idx = i
    return idx

def looks_printed(t):
    return bool(re.search(r'[。，；：、【】（）]', t))

for name in ['板书合集_27考研epsilon-delta题型方法梳理班手稿(高数篇)数学一__eecdc6.jsonl',
             '板书合集_27考研epsilon-delta题型方法梳理班手稿(线代篇)数学一二三__144e26.jsonl']:
    p = os.path.join(r'build\pages', name)
    pages = load(p)
    bad_after = 0
    bad_before = 0
    nofooter = 0
    samples = []
    for pg in pages:
        blocks = pg['blocks']
        fi = footer_idx(blocks)
        if fi < 0:
            nofooter += 1
            continue
        after = blocks[fi+1:]
        before = blocks[:fi+1]
        # 印刷体误落入 after 区
        sapp = [b for b in after if b['text'].count('。') >= 1 or '【例' in b['text']]
        if sapp:
            bad_after += 1
            if len(samples) < 6:
                samples.append((pg['page'], 'AFTER', [b['text'][:80] for b in sapp[:3]]))
        # 手写误落入 before 区(用手写特征:非常见字或纯小写串)
        gb = [b for b in before if not looks_printed(b['text']) and len(b['text']) < 12 and re.search(r'[a-z]{4,}', b['text'])]
        if len(gb) >= 3:
            bad_before += 1
    print(name[:40], 'pages', len(pages), 'nofooter', nofooter,
          'printed-after-footer', bad_after, 'garbage-before-footer', bad_before)
    for s in samples:
        print('   ', s)
