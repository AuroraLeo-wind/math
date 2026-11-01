# -*- coding: utf-8 -*-
"""_ep_audit.py — EP.jsonl 质量审计(只读, 不改产物)。

检查:
  1. schema 必填字段 / 类型 / kind 合法值
  2. id 唯一性与格式
  3. example 卡是否有非空题面
  4. method/symptom 卡是否有空壳(method_chain 与 symptom 全空)
  5. 章节词表外的 chapter 值
  6. 分部统计: 手写来源 vs 印刷来源
  7. 打印随机样本便于人工抽查
"""
import json, os, re, sys, random
from collections import Counter, defaultdict
sys.stdout.reconfigure(encoding='utf-8')

PATH = r'D:\math\kb\cards\EP.jsonl'
REQ = ['id', 'kind', 'subject', 'chapter', 'topic', 'title', 'symptom', 'method_chain',
       'formula', 'pitfall', 'variants', 'source', 'tags', 'confidence', 'raw']
KINDS = {'map', 'method', 'example', 'symptom', 'pitfall', 'theorem'}
ID_RE = re.compile(r'^EP-(GS|XD|GL)-[A-Z]+-\d{3}$')

cards = [json.loads(l) for l in open(PATH, encoding='utf-8') if l.strip()]
print(f'总卡数 {len(cards)}')

bad = defaultdict(list)
ids = Counter()
for c in cards:
    for f in REQ:
        if f not in c:
            bad['缺字段'].append((c.get('id'), f))
    if c.get('kind') not in KINDS:
        bad['kind非法'].append((c.get('id'), c.get('kind')))
    if not ID_RE.match(c.get('id', '')):
        bad['id格式'].append(c.get('id'))
    ids[c.get('id')] += 1
    src = c.get('source') or {}
    for f in ('file', 'page', 'book', 'locator'):
        if f not in src:
            bad['source缺字段'].append((c.get('id'), f))
    if c.get('confidence') not in ('explicit', 'inferred'):
        bad['confidence非法'].append((c.get('id'), c.get('confidence')))
    if not c.get('raw'):
        bad['raw空'].append(c.get('id'))
    if c.get('kind') == 'example':
        stem = c['raw'].split('【题面】')[-1].split('【印刷解析】')[0].split('【手写板书OCR】')[0]
        if len(re.sub(r'\s', '', stem)) < 10:
            bad['example题面过短'].append((c.get('id'), stem[:30]))
    if c.get('kind') in ('method', 'symptom'):
        if not c.get('method_chain') and not c.get('symptom'):
            bad['method空壳'].append(c.get('id'))
    for fld in ('symptom', 'method_chain', 'formula', 'pitfall', 'variants', 'tags'):
        if not isinstance(c.get(fld), list):
            bad['字段非list'].append((c.get('id'), fld))
    if len(c.get('method_chain') or []) > 8:
        bad['链条超8步'].append((c.get('id'), len(c['method_chain'])))

dup = [k for k, v in ids.items() if v > 1]
print(f'重复 id: {len(dup)} {dup[:5]}')
for k, v in bad.items():
    print(f'  {k}: {len(v)}  {v[:5]}')

print('\n-- 分布 --')
print('subject:', dict(Counter(c['subject'] for c in cards)))
print('kind   :', dict(Counter(c['kind'] for c in cards)))
print('conf   :', dict(Counter(c['confidence'] for c in cards)))
print('book   :', dict(Counter(c['source']['book'] for c in cards)))
print('文件数 :', len(set(c['source']['file'] for c in cards)))
print('章节   :', sorted(set((c['subject'], c['chapter']) for c in cards)))

print('\n-- 字段填充率 --')
for fld in ('symptom', 'method_chain', 'formula', 'pitfall'):
    for kind in ('example', 'method', 'symptom'):
        sel = [c for c in cards if c['kind'] == kind]
        if sel:
            filled = sum(1 for c in sel if c[fld])
            print(f'  {kind:8s} {fld:13s} {filled:4d}/{len(sel):4d}')

print('\n-- 手写来源(method 卡 raw 含 OCR 特征) --')
hand = [c for c in cards if c['kind'] in ('method', 'symptom')
        and re.search(r'总传|总佶|总信|总结|口决|口诀|另解|法一|法二', c['raw'])]
print('候选手写方法卡:', len(hand))

print('\n-- 随机 8 张(不同 kind) --')
rnd = random.Random(7)
for kind in ('example', 'method', 'symptom'):
    sel = [c for c in cards if c['kind'] == kind]
    for c in rnd.sample(sel, min(3 if kind == 'example' else 3, len(sel))):
        print('=' * 70)
        print(c['id'], '|', c['kind'], '|', c['title'])
        print('  sym:', c['symptom'][:4])
        print('  mc :', c['method_chain'][:5])
        print('  f  :', c['formula'][:2])
        print('  src:', c['source']['file'][:30], 'p', c['source']['page'])
        print('  raw:', c['raw'][:300].replace('\n', ' ⏎ '))
