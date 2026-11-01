import re
p = r"D:\dsh\resources\app.asar"
data = open(p, "rb").read()
for pat in [rb"dshHome", rb"DSH_HOME", rb"\.dsh\b"]:
    hits = [m.start() for m in re.finditer(pat, data)]
    print(f"\n=== {pat} hits={len(hits)}")
    for h in hits[:8]:
        seg = data[max(0,h-120):h+180].decode("utf-8","replace").replace("\n"," ")
        print("  ...", seg, "...")
