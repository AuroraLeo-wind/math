import re, sys
p = r"D:\dsh\resources\app.asar"
data = open(p, "rb").read()
print("size MB", len(data)//1048576)
pats = [rb"SKILL\.md", rb"skills[/\\]", rb"skillDirs", rb"skillsDir", rb"builtinSkills", rb"\.dsh[/\\]skills"]
for pat in pats:
    hits = [m.start() for m in re.finditer(pat, data)]
    print(f"\n=== {pat} hits={len(hits)}")
    for h in hits[:6]:
        seg = data[max(0,h-160):h+160]
        txt = seg.decode("utf-8", "replace").replace("\n", " ")
        print("  ...", txt, "...")
