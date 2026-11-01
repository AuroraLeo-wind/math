import sys,re
sys.path.insert(0,r"D:\math\scripts")
from collections import Counter
import kb_dx_extract as K
pages = K.load_pages(r"(3_3)--大雪深埋概率论电子版*.jsonl")
chm, m, order = K.build_chapter_index(pages)
cards, stat, preambles = K.collect_cards(pages, chm, set(m)|set(m.values()))
print("preambles",len(preambles))
tu=Counter(); ss=Counter()
for pre in preambles:
    merged=K.merge_fragments(pre["lines"])
    for seg in K.split_segments(merged):
        card, why = K.make_method_card(seg, pre, "概率", tu, ss)
        if card is None:
            body="".join(seg["lines"])
            print("[DROP %s] topic=%s label=%s level=%s | %d 行: %s"%(why, pre.get("topic_label"), seg["label"], seg["level"], len(seg["lines"]), body[:70]))
        elif card["kind"]=="pitfall":
            print("[PITFALL] %s | %s"%(card["id"] or "-", card["title"][:80]))
