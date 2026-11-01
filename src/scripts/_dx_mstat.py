import json
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
ms=[c for c in cards if c["kind"]!="example"]
L=[len(c["title"]) for c in ms]
print("方法卡",len(ms),"| title 长度 min/avg/max:",min(L),round(sum(L)/len(L)),max(L))
print("链非空:",sum(1 for c in ms if c["method_chain"]),"| 公式非空:",sum(1 for c in ms if c["formula"]))
print("pitfall 卡:",[c["id"] for c in ms if c["kind"]=="pitfall"])
for c in sorted(ms,key=lambda x:-len(x["title"]))[:5]: print("  long:",len(c["title"]),c["title"])
