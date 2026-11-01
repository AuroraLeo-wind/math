import json,glob
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
for cid in ("DX-GS-C08-015","DX-GS-C08-016"):
    c=[x for x in cards if x["id"]==cid][0]
    print("="*60); print(cid, c["title"], "p", c["source"]["page"], c["source"]["locator"])
    print(repr(c["raw"]))
f=glob.glob(r"D:\math\build\pages\(3_1)*.jsonl")[0]
pages=[json.loads(l) for l in open(f,encoding="utf-8")]
p=[x for x in pages if x["page"]==69][0]
print("\n==== raw page 69 blocks ====")
for b in sorted(p["blocks"],key=lambda z:(z["y0"],z["x0"])):
    print("  y%4d x%4d | %s"%(b["y0"],b["x0"],b["text"].replace("\n"," / ")[:100]))
