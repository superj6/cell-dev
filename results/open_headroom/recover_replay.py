"""Rebuild an agent's scratch files by replaying its Write/Edit calls, bash heredoc writes, sed -i edits and
python edit heredocs (in order) from its transcript, with the dead /tmp scratch path mapped to a durable directory."""
import json, os, re, subprocess, sys

OLD = "/tmp/claude-1000/-home-jgon-project-ml-cell-dev/aefb0c66-3af5-49c4-936c-154d6434706c/scratchpad/openhr"
NEW = "/home/jgon/project/ml/cell-dev/outputs/openhr"
transcript, prefix = sys.argv[1], sys.argv[2]  # only replay ops touching OLD/<prefix>
ROOT_OLD, ROOT_NEW = f"{OLD}/{prefix}", f"{NEW}/{prefix}"
mp = lambda s: s.replace(OLD, NEW)
log = []

def heredocs(cmd):
    # cat > F <<'EOF' ... EOF   and   cat >> F <<'EOF' ... EOF
    for m in re.finditer(r"cat (>>?) *(\S+) *<<'?(\w+)'?\n(.*?)\n\3(?:\n|$)", cmd, re.S):
        yield m.group(1), m.group(2), m.group(4)

def run_bash(cmd):
    H = None
    m = re.search(r"\bH=(\S+?)(?:;|\s|&&)", cmd)
    if m: H = m.group(1)
    env = dict(os.environ)
    if H: env["H"] = mp(H)
    # 1) heredoc writes
    for op, f, body in heredocs(cmd):
        f = f.replace("$H", H or "$H")
        if not f.startswith(ROOT_OLD): continue
        f = mp(f); os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "a" if op == ">>" else "w") as fh: fh.write(mp(body) + "\n")
        log.append(f"heredoc{op} {f}")
    # 2) sed -i edits
    for m in re.finditer(r"sed -i (['\"])(.*?)\1 ([^\s;&]+)", cmd):
        f = m.group(3).replace("$H", H or "$H")
        cwd = None
        if not f.startswith("/"):
            cd = re.search(r"cd (\S+) &&", cmd)
            cwd = mp(cd.group(1)) if cd else None
            f = os.path.join(cwd or "", f)
        f = mp(f)
        if not f.startswith(ROOT_NEW): continue
        subprocess.run(["sed", "-i", m.group(2), f], check=True)
        log.append(f"sed {f}")
    # 3) python edit heredocs run inside the dir
    cd = re.search(r"cd (\S+) && python3 - <<'EOF'\n(.*?)\nEOF", cmd, re.S)
    if cd and cd.group(1).startswith(ROOT_OLD):
        d = mp(cd.group(1)); body = mp(cd.group(2))
        if "open(" in body and ('"w"' in body or "'w'" in body):
            r = subprocess.run([sys.executable, "-"], input=body, text=True, cwd=d, capture_output=True)
            log.append(f"pyedit in {d}: rc={r.returncode} {r.stderr[-300:]}")

for line in open(transcript):
    d = json.loads(line)
    m = d.get("message", {})
    if not isinstance(m, dict) or not isinstance(m.get("content"), list): continue
    for b in m["content"]:
        if not (isinstance(b, dict) and b.get("type") == "tool_use"): continue
        n, i = b["name"], b["input"]
        fp = i.get("file_path", "")
        if n == "Write" and fp.startswith(ROOT_OLD):
            f = mp(fp); os.makedirs(os.path.dirname(f), exist_ok=True)
            open(f, "w").write(mp(i["content"])); log.append(f"write {f}")
        elif n == "Edit" and fp.startswith(ROOT_OLD):
            f = mp(fp); s = open(f).read(); old, new = mp(i["old_string"]), mp(i["new_string"])
            if old not in s: log.append(f"EDIT MISS {f}: {old[:60]!r}"); continue
            s = s.replace(old, new) if i.get("replace_all") else s.replace(old, new, 1)
            open(f, "w").write(s); log.append(f"edit {f}")
        elif n == "Bash" and ROOT_OLD in i.get("command", "") or (n == "Bash" and "$H" in i.get("command", "")):
            run_bash(i["command"])
print("\n".join(log))
