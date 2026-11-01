import json,re
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
BOIL=("扫码了解更多课程","27考研：epsilon","关注公主号","抖音/小红书","By epsilon-delta","大雪深埋强化课讲义")
leak=[c["id"] for c in cards if any(b in c["raw"] for b in BOIL)]
print("raw 含页眉页脚噪声:",len(leak), leak[:5])
gl=[c for c in cards if c["subject"]=="概率"]
print("概率卡:",len(gl),"| 含【解析】:",sum(1 for c in gl if "【解析】" in c["raw"]),"| 空解析:",sum(1 for c in gl if "【解析】" not in c["raw"]))
# 选项完整性抽查:选择题应含 A. B. C. D.
sel=[c for c in cards if "四选一选择题" in " ".join(c["symptom"])]
miss=[c["id"] for c in sel if not (re.search(r"\bA[.．]",c["raw"]) and re.search(r"\bD[.．]",c["raw"]))]
print("选择题卡:",len(sel),"| 缺 A./D. 选项:",len(miss), miss[:5])
# raw 结构
bad=[c["id"] for c in cards if not c["raw"].startswith("【题面】")]
print("raw 不以【题面】开头:",len(bad))
# source 一致性
nopage=[c["id"] for c in cards if c["source"].get("page") is None]
print("缺 page:",len(nopage))
print("page_end < page:",sum(1 for c in cards if c["source"]["page_end"]<c["source"]["page"]))
# id 前缀
print("id 前缀:",sorted({c["id"].split("-")[1] for c in cards}))
print("最大 raw:",max(len(c["raw"]) for c in cards))
