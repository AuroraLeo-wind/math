import json,glob,re
f=glob.glob(r"D:\math\build\pages\(3_1)*.jsonl")[0]
pages=[json.loads(l) for l in open(f,encoding="utf-8")]
for idx in (2,7,23,34,38,50,56,62,75,82,91,103,111,118,128,145,147):
    p=pages[idx]
    cand=[(round(b["y0"],1),round(b["x0"]),round(b["x1"]),b["text"].replace("\n","/")[:24]) for b in p["blocks"] if b["y0"]<110 and b["y1"]>40]
    print("p%-3d"%idx, cand[:4])
