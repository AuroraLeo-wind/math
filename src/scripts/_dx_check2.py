import json
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
for cid in ("DX-GS-C08-015","DX-GS-C08-016"):
    c=[x for x in cards if x["id"]==cid][0]
    print(cid,"|",c["title"],"| raw_len",len(c["raw"]))
