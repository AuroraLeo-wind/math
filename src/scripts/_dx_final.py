import json
from collections import Counter
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
n=len(cards)
print("DX 卡片:",n)
print("科目:",dict(Counter(c["subject"] for c in cards)))
print("confidence:",dict(Counter(c["confidence"] for c in cards)))
print("id 唯一:",len({c["id"] for c in cards})==n)
print("必填齐:",all(all(k in c for k in ("id","kind","subject","chapter","topic","title","source","confidence","raw")) for c in cards))
steps=[len(c["method_chain"]) for c in cards if c["method_chain"]]
print("method_chain 非空:",len(steps),f"({len(steps)/n:.1%})","max",max(steps))
print("raw 最短/最长:",min(len(c["raw"]) for c in cards),max(len(c["raw"]) for c in cards))
