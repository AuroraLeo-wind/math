import json,glob,os
f=glob.glob(r"D:\math\build\pages\(3_1)*.jsonl")[0]
pages=[json.loads(l) for l in open(f,encoding="utf-8")]
print("total pages", len(pages))
for p in pages[:14]:
    t=p["text"]
    print("="*30, "page", p["page"], "len", len(t), "blocks", len(p["blocks"]))
    print(t[:900])
