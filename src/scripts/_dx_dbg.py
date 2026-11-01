import json,glob,re
BOIL=("扫码了解更多课程","27考研：epsilon","关注公主号","抖音/小红书","By epsilon-delta")
for tag,pat in [("GS",r"D:\math\build\pages\(3_1)*.jsonl"),("GL3",r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl")]:
    ps=[json.loads(l) for l in open(glob.glob(pat)[0],encoding="utf-8")]
    cur=None; cards=[]
    for p in ps:
        for line in p["text"].split("\n"):
            t=line.strip()
            if not t or any(b in t for b in BOIL) or re.fullmatch(r"\d{1,3}",t): continue
            if re.match(r"【例\s*\d+",t):
                cur={"s":[t],"a":[],"p":p["page"]}; cards.append(cur)
            elif cur is not None:
                (cur["a"] if cur["a"] else cur["s"]).append(t)
    short=[(c["p"],"".join(c["s"])[:100]) for c in cards if len("".join(c["s"]))<45]
    print("####",tag,"cards",len(cards),"short stems",len(short))
    for x in short[:12]: print("   p%-3d %s"%x)
    openend=[(c["p"],"".join(c["s"])[-40:]) for c in cards if not re.search(r"[。．.；;？?）)]$","".join(c["s"]).strip())]
    print("   无终止符的题面尾:",len(openend))
    for x in openend[:8]: print("      p%-3d ...%s"%x)
