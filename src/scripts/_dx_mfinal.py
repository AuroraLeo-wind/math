import json,re,random
from collections import Counter
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
REQ=("id","kind","subject","chapter","topic","title","symptom","method_chain","source","confidence","raw")
n=len(cards)
print("DX 总卡:",n,"| kind:",dict(Counter(c["kind"] for c in cards)))
print("id 唯一:",len({c["id"] for c in cards})==n,"| 必填齐:",all(all(k in c for k in REQ) for c in cards))
print("id 形态:",sorted({re.sub(r"\d+","#",c["id"]) for c in cards})[:4])
bad=[c["id"] for c in cards if len(c["method_chain"])>8]
print("超过 8 步的卡:",len(bad))
steps=[len(c["method_chain"]) for c in cards if c["method_chain"]]
print("链非空:",len(steps),f"({len(steps)/n:.1%})","| 平均",round(sum(steps)/len(steps),1),"步 | 最长",max(steps))
long=[s for c in cards for s in c["method_chain"] if len(s)>41]
print("链条单步 >41 字的:",len(long))
print("inferred_fields 分布:",dict(Counter(f for c in cards for f in c.get("inferred_fields",[]))))
ms=[c for c in cards if c["kind"]!="example"]
print("方法卡:",len(ms),"| 其中 pitfall:",sum(1 for c in ms if c["kind"]=="pitfall"))
print("方法卡按章:",dict(Counter(c["chapter"] for c in ms)))
random.seed(5)
for c in random.sample(ms,3):
    print("="*80)
    print(c["id"],"|",c["kind"],"|",c["title"])
    print(f'   p{c["source"]["page"]}->{c["source"]["page_end"]} | {c["source"]["locator"]}')
    print("   symptom:",c["symptom"])
    print("   链:")
    for i,s in enumerate(c["method_chain"],1): print(f"     {i}. {s}")
    print("   公式:",c["formula"][:2])
    if c["pitfall"]: print("   陷阱:",c["pitfall"])
    print("   raw全文:")
    for ln in c["raw"].split("\n"): print("     |",ln)
