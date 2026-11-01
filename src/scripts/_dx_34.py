import sys
sys.path.insert(0,r"D:\math\scripts")
import kb_dx_extract as K
for pat,name in ((r"(3_4)*.jsonl","3.4 概率做题本"),(r"(3_3)--大雪深埋概率论电子版*.jsonl","3.3 概率含解析")):
    pages=K.load_pages(pat)
    chm,m,order=K.build_chapter_index(pages)
    cards,stat,pre=K.collect_cards(pages,chm,set(m)|set(m.values()))
    print(name,"| 题型标题:",stat["题型标题"],"| 铺垫段:",len(pre),"| 非例块行:",stat["非例块丢弃"])
