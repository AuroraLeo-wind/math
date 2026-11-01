import sys,re
sys.path.insert(0,r"D:\math\scripts")
import kb_dx_extract as K
pages = K.load_pages(r"(3_3)--大雪深埋概率论电子版*.jsonl")
chm, m, order = K.build_chapter_index(pages)
segs=[]; cur=None; topic=None
for p in pages:
    ch=chm.get(p["page"])
    for ln in K.clean_lines(p, K.title_block(p)):
        if K.is_topic_heading(ln):
            topic=K.TOPIC_RE.sub("",ln).strip().rstrip("：: ")
            segs.append({"topic":topic,"chapter":ch,"page":p["page"],"page_end":p["page"],"lines":[]})
            cur=None; continue
        if K.EXAMPLE_RE.match(ln):
            cur="example"; continue
        if cur is None:
            if segs and ln.strip():
                segs[-1]["lines"].append(ln); segs[-1]["page_end"]=p["page"]
        elif "【解析】" in ln: cur="analysis"
tot=sum(len(s["lines"]) for s in segs)
print("段数",len(segs),"总行数",tot)
for s in segs:
    print("="*72)
    print("【%s】%s p%s->p%s | %d 行 %d 字"%(s["topic"],s["chapter"],s["page"],s["page_end"],len(s["lines"]),sum(len(x) for x in s["lines"])))
    for x in s["lines"]: print("   |",x[:105])
