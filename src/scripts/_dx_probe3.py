import json,glob,re,unicodedata
def load(pat):
    f=glob.glob(pat)[0]
    return f,[json.loads(l) for l in open(f,encoding="utf-8")]
f3,p3=load(r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl")
f4,p4=load(r"D:\math\build\pages\(3_4)*.jsonl")
def items(pages):
    out=[]
    cur=None
    for p in pages:
        for b in p["blocks"]:
            t=b["text"].strip()
            m=re.match(r"【例\s*(\d+)\s*】",t)
            if m:
                cur={"no":int(m.group(1)),"page":p["page"],"parts":[t]}
                out.append(cur)
            elif cur is not None:
                cur["parts"].append(t)
    return [ {**c, "raw":"\n".join(c["parts"])} for c in out]
a=items(p3); b=items(p4)
print("3.3 items",len(a),"3.4 items",len(b))
def norm(s): return re.sub(r"\s+","",s)
for i in range(min(8,len(a))):
    print("---",i, "3.3例",a[i]["no"],"p",a[i]["page"],"len",len(a[i]["raw"]),"| 3.4例",b[i]["no"] if i<len(b) else None,"p",b[i]["page"] if i<len(b) else None,"len",len(b[i]["raw"]) if i<len(b) else None)
    if i<len(b):
        s1=norm(a[i]["raw"])[:70]; s2=norm(b[i]["raw"])[:70]
        print("   same_prefix:", s1[:50]==s2[:50])
        print("   A:",s1)
        print("   B:",s2)
# header geometry of 3.3 page1
p=p3[1]
print("\n3.3 p1 blocks geom:", [(round(x["y0"],1),round(x["y1"],1),x["text"].replace(chr(10),"/")[:40]) for x in sorted(p["blocks"],key=lambda z:(z["y0"],z["x0"]))][:5])
print("3.3 p1 blocks tail:", [(round(x["y0"],1),round(x["y1"],1),x["text"].replace(chr(10),"/")[:40]) for x in sorted(p["blocks"],key=lambda z:(z["y0"],z["x0"]))][-4:])
print("h=",p["h"])
