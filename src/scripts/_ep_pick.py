# -*- coding: utf-8 -*-
"""_ep_pick.py — 挑"方法总结"代表卡(只读)。"""
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
cards = [json.loads(l) for l in open(r'D:\math\kb\cards\EP.jsonl', encoding='utf-8')]

KW = re.compile(r'(三板斧|总结|口诀|口决|框架|判别|方法|思路|套路|模板|步骤|原则|法则|结论)')
picked = []
for c in cards:
    if c['kind'] != 'method':
        continue
    if len(c['method_chain']) < 3:
        continue
    txt = c['title'] + ' '.join(c['method_chain'])
    if not KW.search(txt):
        continue
    # 要求链条里至少 3 条带中文实义(≥5 字)
    solid = [x for x in c['method_chain'] if len(re.findall(r'[\u4e00-\u9fff]', x)) >= 5]
    if len(solid) < 3:
        continue
    picked.append((len(solid), len(c['method_chain']), c))

picked.sort(key=lambda x: (-x[0], -x[1]))
seen_ch = set()
print(f'候选 {len(picked)} 张, 按章去重后展示:')
shown = 0
for solid, n, c in picked:
    if c['chapter'] in seen_ch:
        continue
    seen_ch.add(c['chapter'])
    shown += 1
    print('=' * 76)
    print(f"{c['id']}  [{c['chapter']}/{c['topic']}]  {c['title']}")
    print('  symptom:', c['symptom'][:3])
    for i, s in enumerate(c['method_chain'][:6], 1):
        print(f'   {i}. {s[:90]}')
    print('  formula:', c['formula'][:2])
    print('  pitfall:', c['pitfall'][:2])
    print('  src:', c['source']['file'][:34], 'p', c['source']['page'])
    if shown >= 14:
        break
