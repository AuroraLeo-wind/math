import json
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
ms=[c for c in cards if c["kind"]!="example"]
st=[s for c in ms for s in c["method_chain"]]
print("方法卡链条步数:",len(st),"| 最长单步:",max(len(s) for s in st),"| >41 字的步:",sum(1 for s in st if len(s)>41))
ex=[s for c in cards if c["kind"]=="example" for s in c["method_chain"]]
print("例题卡链条步数:",len(ex),"| 最长单步:",max(len(s) for s in ex) if ex else 0)
print("方法卡 title 示例:")
for c in ms[:3]+ms[-3:]: print("  ",len(c["title"]),c["title"][:80])
