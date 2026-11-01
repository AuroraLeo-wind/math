# -*- coding: utf-8 -*-
"""_ep_report.py — 产出交付汇报用的统计(只读)。"""
import json
import re
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')
cards = [json.loads(l) for l in open(r'D:\math\kb\cards\EP.jsonl', encoding='utf-8')]

K = ['example', 'method', 'symptom', 'pitfall']
print(f'EP 总卡数 {len(cards)}  唯一 id {len(set(c["id"] for c in cards))}  源文件 {len(set(c["source"]["file"] for c in cards))}')
print('kind   ', dict(Counter(c['kind'] for c in cards)))
print('conf   ', dict(Counter(c['confidence'] for c in cards)))
print('subject', dict(Counter(c['subject'] for c in cards)))
print('短raw(<30):', sum(1 for c in cards if len(c['raw']) < 30),
      ' 超8步:', sum(1 for c in cards if len(c['method_chain']) > 8))
print()

stat = defaultdict(Counter)
for c in cards:
    stat[(c['subject'], c['chapter'])][c['kind']] += 1
order = {'高数': 0, '线代': 1, '概率': 2}
print('| 科目 | 章 | 合计 | ' + ' | '.join(K) + ' |')
print('| --- | --- | --- | ' + ' | '.join(['---'] * len(K)) + ' |')
for k in sorted(stat, key=lambda x: (order[x[0]], -sum(stat[x].values()))):
    c = stat[k]
    print('| ' + ' | '.join([k[0], k[1], str(sum(c.values()))] + [str(c[x]) for x in K]) + ' |')
tot = Counter(c['kind'] for c in cards)
print('| 全部 | - | ' + ' | '.join([str(len(cards))] + [str(tot[x]) for x in K]) + ' |')

print()
print('-- 填充率 --')
for kind in K:
    sel = [c for c in cards if c['kind'] == kind]
    if not sel:
        continue
    for fld in ('symptom', 'method_chain', 'formula', 'pitfall'):
        print(f'  {kind:8s}{fld:13s}{sum(1 for c in sel if c[fld]):5d}/{len(sel):5d}')

print()
print('-- 手稿/讲义 vs 补充板书 --')
for tag in ('手稿·高数篇', '手稿·线代篇', '讲义·概率篇', '补充板书'):
    sel = [c for c in cards if tag in c['tags']]
    print(f'  {tag}: {len(sel)}  ' + str(dict(Counter(c["kind"] for c in sel))))

print()
print('-- 知识链完整(method_chain>=2 且 formula 或 symptom 非空)的 method 卡 --')
good = [c for c in cards if c['kind'] == 'method' and len(c['method_chain']) >= 2
        and (c['formula'] or c['symptom'])]
print('数量:', len(good))
for c in good[:12]:
    print(' ', c['id'], '|', c['title'][:76])
    print('     mc:', ' → '.join(c['method_chain'][:4])[:150])
