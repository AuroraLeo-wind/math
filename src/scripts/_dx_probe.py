import json,glob,re
files = {
 "3.1 高数": r"D:\math\build\pages\(3_1)*.jsonl",
 "3.2 线代": r"D:\math\build\pages\(3_2)*.jsonl",
 "3.3 概率含解析": r"D:\math\build\pages\(3_3)--大雪深埋概率论电子版*.jsonl",
 "3.4 概率做题本": r"D:\math\build\pages\(3_4)*.jsonl",
}
for k,g in files.items():
    f=glob.glob(g)[0]
    pages=[json.loads(l) for l in open(f,encoding="utf-8")]
    empty=[p["page"] for p in pages if not p["text"].strip()]
    alltext="\n".join(p["text"] for p in pages)
    ex=len(re.findall(r"【例\s*\d+", alltext))
    print(k, "| file:", f.split("\\")[-1])
    print("   pages", len(pages), "empty", len(empty), "例count", ex)
    print("   解析 occurrences", alltext.count("解析"), "| 【解】", alltext.count("【解】"))
    print("   empty pages:", empty[:40], "..." if len(empty)>40 else "")
    print()
