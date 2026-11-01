import sys,re
sys.path.insert(0,r"D:\math\scripts")
import kb_dx_extract as K
pages = K.load_pages(r"(3_3)--大雪深埋概率论电子版*.jsonl")
chm, m, order = K.build_chapter_index(pages)
print("chapters:", order)
buf=[]; cur=None; topic=None; sections=[]
for p in pages:
    ch=chm.get(p["page"]); title=K.title_block(p)
    for ln in K.clean_lines(p, title):
        if K.is_topic_heading(ln):
            topic=K.TOPIC_RE.sub("",ln).strip().rstrip("：: ")
            sections.append({"topic":topic,"chapter":ch,"page":p["page"],"lines":[]})
            continue
        if K.EXAMPLE_RE.match(ln):
            continue
        if ln.strip():
            # 只统计"题型标题之后到第一个例之前"
            if sections and sections[-1]["lines"] is not None:
                sections[-1]["lines"].append(ln)
# 截断到第一个例之前:重新按例号切
for p in pages:
    pass
print("题型段数:", len(sections))
for s in sections:
    print("="*70)
    print("【%s】 chapter=%s p%s lines=%d chars=%d"%(s["topic"],s["chapter"],s["page"],len(s["lines"]),sum(len(x) for x in s["lines"])))
    for x in s["lines"][:14]: print("   |",x[:110])
