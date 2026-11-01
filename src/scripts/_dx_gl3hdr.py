import json,glob,re
f=glob.glob(r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl")[0]
pages=[json.loads(l) for l in open(f,encoding="utf-8")]
for p in pages:
    hdr=[(round(b["y0"]),round(b["x0"]),round(b["x1"]),b["text"].replace("\n","/")) for b in p["blocks"] if b["y1"]<=40]
    title=[(round(b["y0"]),b["text"].replace("\n","/")[:40]) for b in p["blocks"] if 40<b["y0"]<75]
    print("p%-3d HDR=%s TITLE=%s"%(p["page"],hdr,title[:2]))
