import json
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
gl=[c for c in cards if c["subject"]=="概率"]
empty=[c for c in gl if not c["method_chain"]]
print("empty",len(empty))
for c in empty[:6]:
    ana=c["raw"].split("【解析】")[-1]
    print("="*66); print(c["id"],c["title"]); print("  ana:",ana[:260].replace("\n"," ⏎ "))
