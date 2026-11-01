import json,random
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
gl=[c for c in cards if c["method_chain"]]
print("有链条的卡:",len(gl))
random.seed(31)
for c in random.sample(gl,8):
    print("="*66); print(c["id"],c["title"])
    for i,s in enumerate(c["method_chain"],1): print("   %d. %s"%(i,s))
