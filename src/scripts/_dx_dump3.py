import json,glob,re
f31=glob.glob(r"D:\math\build\pages\(3_1)*.jsonl")[0]
pages=[json.loads(l) for l in open(f31,encoding="utf-8")]
p=pages[2]
print("keys of page:", list(p.keys()))
print("block sample:", json.dumps(p["blocks"][:4],ensure_ascii=False,indent=1))
print("..." )
print("block last 4:", json.dumps(p["blocks"][-4:],ensure_ascii=False,indent=1))
print("h,w:",p["h"],p["w"])
# tail pages
for q in pages[-6:]:
    print("="*25,"page",q["page"],"len",len(q["text"]))
    print(q["text"][:500])
