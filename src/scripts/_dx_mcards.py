import json
cards=[json.loads(l) for l in open(r"D:\math\kb\cards\DX.jsonl",encoding="utf-8")]
ms=[c for c in cards if c["kind"]!="example"]
print("方法卡",len(ms))
for c in ms:
    print("-"*100)
    print(f'{c["id"]} [{c["kind"]}] {c["title"][:96]}')
    print(f'   p{c["source"]["page"]}->{c["source"]["page_end"]} | topic={c["topic"]} | 链{len(c["method_chain"])}步 | 公式{len(c["formula"])}')
    for i,s in enumerate(c["method_chain"],1): print(f'   {i}. {s}')
