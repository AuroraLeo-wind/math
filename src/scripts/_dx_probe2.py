import json,glob,re
for tag,pat in [("GS",r"D:\math\build\pages\(3_1)*.jsonl"),("XD",r"D:\math\build\pages\(3_2)*.jsonl"),("GL3",r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl"),("GL4",r"D:\math\build\pages\(3_4)*.jsonl")]:
    f=glob.glob(pat)[0]
    pages=[json.loads(l) for l in open(f,encoding="utf-8")]
    alltext="\n".join(p["text"] for p in pages)
    print("#### ",tag, "答案:",alltext.count("答案"), "| 解析:",alltext.count("解析"))
    # page -> top header
    rows=[]
    for p in pages:
        bl=p["blocks"]; h=p["h"]
        top=[b["text"].replace("\n","/") for b in bl if b["y0"]<70]
        bot=[b["text"].replace("\n","/") for b in bl if b["y0"]>h-70]
        rows.append((p["page"],top,bot))
    prev=None
    for pg,top,bot in rows[:6]:
        print("  p%-3d TOP=%s | BOT=%s"%(pg,top,bot))
    print("  ... chapter-ish transitions:")
    last=None
    for pg,top,bot in rows:
        key=tuple(top)
        if key!=last:
            print("   p%-3d TOP=%s BOT=%s"%(pg,top,bot))
            last=key
    print()
