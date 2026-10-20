"""A9 network diagnosis: one sandboxed claude -p Bash call that reports whether outbound HTTPS to a non-gateway host
is refused, under the given settings variant. Prints flags only (no environment values).

  python3 -I net_probe.py [variant]      # variant: base | no_allowlist | shim
"""
import json
import subprocess
import sys
from pathlib import Path

EX = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EX / "scripts"), str(EX / "common")]
import sandbox as SB  # noqa: E402

variant = sys.argv[1] if len(sys.argv) > 1 else "base"
ws = SB.OPT_ROOT / "netprobe"
ws.mkdir(parents=True, exist_ok=True)
sf = SB.settings_file("netprobe", ws)
s = json.loads(sf.read_text())
if variant == "no_allowlist":
    s["sandbox"]["network"] = {"allowedDomains": []}
sf.write_text(json.dumps(s))
cmd_text = ("echo net_var=${DEVAGENT_BWRAP_NETWORK:-unset}; echo proxy_set=$([ -n \"$HTTPS_PROXY$https_proxy\" ] && echo yes || echo no); "
            "python3 -c \"import urllib.request; print('urllib', urllib.request.urlopen('https://example.com', timeout=10).status)\" 2>&1 | tail -1; "
            "python3 -c \"import socket; s=socket.create_connection(('93.184.215.14', 443), timeout=8); print('raw_tcp connected')\" 2>&1 | tail -1; "
            "echo sandbox_probe=$(cat /proc/self/status | grep -c Landlock)")
prompt = f"Run exactly this one Bash command and paste its raw output, nothing else:\n\n{cmd_text}"
env = SB.claude_env()
src = [] if variant == "shim" else ["--setting-sources", ""]
r = subprocess.run(["claude", "-p", prompt, "--settings", str(sf), *src, "--allowedTools", "Bash",
                    "--max-turns", "3", "--output-format", "json", "--model", "aws/claude-sonnet-5-5",
                    "--permission-mode", "acceptEdits"], cwd=ws, env=env, capture_output=True, text=True, timeout=600)
out = json.loads(r.stdout.strip().splitlines()[-1]).get("result", "")
keep = [l for l in out.splitlines() if l.strip().split("=")[0].split(" ")[0] in
        ("net_var", "proxy_set", "urllib", "raw_tcp", "sandbox_probe") or "Error" in l or "rror:" in l]
print(json.dumps({"variant": variant, "env_passed_DEVAGENT_BWRAP_NETWORK": env.get("DEVAGENT_BWRAP_NETWORK"),
                  "settings_env": s.get("env"), "lines": keep[:12]}, indent=1))
