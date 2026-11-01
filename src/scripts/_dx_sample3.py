import json,random
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
random.seed(27); s=random.sample(cards,3)
for c in s:
    stem=c["raw"].split("【解析】")[0].replace("【题面】","").strip()
    print(f'{c["id"]} | {c["title"]}')
    print(f'   p{c["source"]["page"]}->p{c["source"]["page_end"]} | 题面{len(stem)}字 | 链{len(c["method_chain"])}步 | 解析{"有" if "【解析】" in c["raw"] else "无"}')
    print("   stem:", " / ".join(x for x in stem.split("\n") if x.strip())[:150])
    print()
print("=== 一张概率卡 raw 全文(节选前 700 字) ===")
gl=[c for c in cards if c["subject"]=="概率" and c["method_chain"]][0]
print(gl["id"], gl["title"]); print(gl["raw"][:700])
print("...")
print("=== 该卡 method_chain ===")
for i,x in enumerate(gl["method_chain"],1): print(f"  {i}. {x}")
