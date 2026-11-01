import json, glob, collections, sys
sys.stdout.reconfigure(encoding="utf-8")
cards=[]
for p in sorted(glob.glob("kb/cards/*.jsonl")):
    for l in open(p,encoding="utf-8"):
        l=l.strip()
        if l: cards.append((p,json.loads(l)))
ids=collections.Counter(c["id"] for _,c in cards)
dup=[i for i,n in ids.items() if n>1]
print("dup ids:",len(dup),"total cards:",len(cards))
# 看一个重复 id 的两张卡来源
for d in dup[:3]:
    print("\n==",d)
    for p,c in cards:
        if c["id"]==d:
            print("   file:",p,"| src:",c["source"]["file"],"p",c["source"]["page"],"| kind:",c["kind"],"| title:",c["title"][:40])
# 按文件统计 id 前缀
pref=collections.Counter()
for p,c in cards:
    pref[(p.split("\\")[-1], c["id"].split("-")[1] if "-" in c["id"] else "?")]+=1
print("\nfile x subject-code:", dict(pref))
# DX 抽样
dx=[c for _,c in cards if c["id"].startswith("DX")]
print("\nDX sample:")
for c in dx[:2]:
    print(json.dumps({k:c[k] for k in ("id","kind","chapter","topic","title","confidence")},ensure_ascii=False))
    print("  raw:",c["raw"][:300].replace("\n"," / "))
