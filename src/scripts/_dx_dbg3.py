import json,random
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
print("total",len(cards))
gl=[c for c in cards if c["subject"]=="概率"]
random.seed(7)
for c in random.sample(gl,4):
    print("="*70)
    print(c["id"], c["title"])
    print(" chain:", len(c["method_chain"]))
    for i,s in enumerate(c["method_chain"],1): print("   %d. %s"%(i,s))
    print(" formula:", c["formula"])
    print(" pitfall:", c["pitfall"])
print("\n\n#### 跨页卡样例")
xpage=[c for c in cards if c["source"]["page_end"]>c["source"]["page"]]
print("count",len(xpage))
for c in xpage[:3]:
    print("="*70); print(c["id"],c["title"],"p%d->p%d"%(c["source"]["page"],c["source"]["page_end"]))
    print(c["raw"][:600])
