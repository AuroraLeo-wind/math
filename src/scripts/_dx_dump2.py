import json,glob
f=glob.glob(r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl")[0]
pages=[json.loads(l) for l in open(f,encoding="utf-8")]
for p in pages[1:6]:
    print("="*30,"page",p["page"],"len",len(p["text"]))
    print(p["text"][:1400])
