import json
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
ms=[c for c in cards if c["kind"]!="example"]
print("带 pitfall 字段的方法卡:",sum(1 for c in ms if c["pitfall"]))
for c in ms:
    if c["pitfall"]:
        print("  -",c["id"],"|",c["pitfall"][0][:90])
print()
print("含『得不到』的卡:")
for c in ms:
    if "得不到" in c["raw"]:
        print("  -",c["id"],c["kind"],"|",c["title"][:70])
        print("     raw头:",c["raw"][:120].replace("\n"," ⏎ "))
