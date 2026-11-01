import sys, re
sys.path.insert(0,r"D:\math\scripts")
import kb_dx_extract as K
pages = K.load_pages(r"(3_1)*.jsonl")
chm, m, order = K.build_chapter_index(pages)
print("hdr2title:", m)
cards, stat = K.collect_cards(pages, chm, set(m)|set(m.values()))
print("cards", len(cards), stat)
for c in cards:
    if c["chapter"]=="数列极限" and 16 <= c["no"] <= 19:
        print("="*20, "例", c["no"], "p", c["page"], "->", c["page_end"])
        for ln in c["stem"]:
            print("   S|", ln[:90])
# 检查所有"结尾开符号"的stem
open_ends=[(c["chapter"],c["no"],c["stem"][-1][:40]) for c in cards if c["stem"] and K.OPEN_TAIL_RE.search("".join(c["stem"]).strip())]
print("\n开符号结尾的卡:", len(open_ends))
for x in open_ends[:15]: print("   ", x)
