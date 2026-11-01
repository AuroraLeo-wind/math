import json
from collections import Counter
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
c=Counter(x["topic"] for x in cards if x["subject"]=="高数")
for k,v in c.most_common(12): print("  ",k,v)
print("  ...共",len(c),"种 topic")
print("topic==chapter 的卡:",sum(1 for x in cards if x["topic"]==x["chapter"]))
