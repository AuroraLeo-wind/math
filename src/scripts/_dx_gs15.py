import json,glob
f=glob.glob(r"D:\math\build\pages\(3_1)*.jsonl")[0]
pages=[json.loads(l) for l in open(f,encoding="utf-8")]
for p in pages[14:23]:
    print("="*30,"page",p["page"])
    for b in sorted(p["blocks"],key=lambda z:(z["y0"],z["x0"])):
        print("   y%4d %s"%(b["y0"],b["text"].replace("\n"," / ")[:110]))
