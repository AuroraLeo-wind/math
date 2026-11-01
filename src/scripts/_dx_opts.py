import json,re
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
OPT=re.compile(r"[（(]([ABCD])[)）]|(?:^|\s)([ABCD])[.．、]")
def labels(t): return {m.group(1) or m.group(2) for m in OPT.finditer(t)}
sel=[c for c in cards if "四选一选择题" in " ".join(c["symptom"])]
bad=[c["id"] for c in sel if len(labels(c["raw"].split("【解析】")[0]) & set("ABCD"))<3]
print("选择题卡:",len(sel),"| 误判:",len(bad), bad[:5])
# 反向:含 ABCD 选项但没被标为选择题
missed=[c["id"] for c in cards if "四选一选择题" not in " ".join(c["symptom"]) and len(labels(c["raw"].split("【解析】")[0]) & set("ABCD"))>=3]
print("漏标选择题:",len(missed), missed[:5])
