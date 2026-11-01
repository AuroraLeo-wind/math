import json, struct, sys
p = r"D:\dsh\resources\app.asar"
with open(p, "rb") as f:
    head = f.read(16)
    # asar: 4 bytes uint32 (4), 4 bytes header size pickle, 4 bytes json size, 4 bytes json length
    a, b, c, d = struct.unpack("<IIII", head)
    f.seek(16)
    raw = f.read(c)
try:
    hdr = json.loads(raw.decode("utf-8"))
except Exception as e:
    print("header decode fail", e); sys.exit()
out = []
def walk(node, prefix=""):
    for k, v in node.get("files", {}).items():
        path = prefix + "/" + k
        if "files" in v:
            walk(v, path)
        else:
            out.append(path)
walk(hdr)
print("total entries:", len(out))
kw = [x for x in out if "skill" in x.lower()]
print("skill entries:", len(kw))
for x in kw[:40]:
    print("  ", x)
