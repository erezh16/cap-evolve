# Working as an agent inside a devagent workspace

**For:** a coding agent (Claude Code, and its sub-agents) running inside a devagent workspace
container, and the operator who configures it. Everything the agent is asked to check, it
checks from inside its own container: nothing here assumes access to the cluster, the
runtime or the host. Two things work differently here than on an
ordinary Linux machine, and an agent that does not know them loses work: **how sub-agents
and shell commands can be isolated**, and **how much memory the container has before it is
killed**. Each section says what is true, what to do, and what can be changed.

Written 2026-10-16 against the image built from the `tooling` branch (Claude Code CLI
2.1.270). Statements marked *measured* were run in workspaces on podman, docker and
OpenShift; the evidence is in [TOOLING.md §9.10–§9.13](TOOLING.md).

---

## 1. Sub-agent isolation: Claude Code's sandbox in a container

### 1.1 What it is

Claude Code's **sandbox** (`sandbox.enabled` in settings, or `/sandbox`) confines the
**shell commands** an agent runs: the `Bash` and `Monitor` tools and every process they
start. Sub-agents run in the same process as the agent that spawned them and use the same
sandbox configuration, so **a sub-agent's shell commands are confined exactly as its
parent's are**. That is the mechanism for keeping a sub-agent away from files: the sandbox
for its shell, and permission rules for its file tools (§1.3).

It is **off until someone turns it on**. Nothing about a workspace enables it by itself.

### 1.2 What it confines, and what it does not

| Confined (shell commands, the agent's and every sub-agent's) | Not confined |
|---|---|
| **Writes**: only the working directory, Claude's temp directory and the paths settings allow; everything else is denied by the kernel | **Claude's own file tools**: `Read`, `Edit`, `Write`, `Grep`, `Glob` run outside the sandbox. Use `permissions.deny` rules for them (§1.3) |
| **Masked files**: `.claude/settings.json`, hooks, skills, agents, `.mcp.json`, `.bashrc`, `.gitconfig` and the like in the working directory read as empty; a write to one is discarded (under bubblewrap, refused), and nothing can be created under a masked directory | `WebFetch`, `WebSearch` and MCP servers: governed by permissions, not the sandbox |
| **Unix sockets**: a command cannot create one, so it cannot drive tmux, the devagent broker or an agent socket to run something outside the sandbox | Processes started outside the agent (the operator's shells, tmux sessions, the VS Code server) |
| **Reads**: only of what `sandbox.filesystem` denies | **Everything else is readable**: by default a sandboxed command can read most of the filesystem |
| **Network**: see §1.5. Under landrun + proot it is open by default | Commands Claude runs **unsandboxed** after a sandboxed attempt fails, if `allowUnsandboxedCommands` is true (the default) and the user approves |

### 1.3 How to enable it

In `~/.claude/settings.json` (on the laptop: `devctl` syncs it into every workspace) or
per run with `--settings`:

```json
{
  "sandbox": {
    "enabled": true,
    "allowUnsandboxedCommands": false,
    "failIfUnavailable": true
  },
  "permissions": {
    "deny": ["Read(//workspace/secrets/**)", "Edit(//workspace/secrets/**)"]
  }
}
```

* `allowUnsandboxedCommands: false` stops Claude retrying a failed command outside the
  sandbox. Without it, any command the sandbox refuses can be rerun unconfined on approval.
* `failIfUnavailable: true` makes a sandbox that cannot start a refusal: no command runs,
  rather than every command running unconfined.
* The `deny` rules are what keep a sub-agent's **file tools** away from a path. The sandbox
  alone does not. `//` starts an absolute path in a permission rule; a single `/` is
  relative to the settings file.
* `sandbox.filesystem` settings narrow what commands may read or write further.
  `enableWeakerNestedSandbox` is **not needed** in a devagent workspace (§1.4).

To see, from inside the workspace, whether and how the sandbox would run:
`devagent-bwrap --devagent-tier --unshare-net --ro-bind / / --dev /dev --proc /proc -- true`
prints the tier it would use, or why neither can. (The operator sees the same from the
laptop, in `devctl doctor -w <ws>`, lines `bwrap_shim` and `bwrap_userns`.)

### 1.4 Why it is different here: bubblewrap, and the stand-in

On an ordinary Linux machine Claude Code's sandbox is **bubblewrap**: a private mount,
PID and network namespace per command. bubblewrap needs an unprivileged **user namespace**,
and every runtime devagent puts workspaces on refuses one (*measured*): docker's and OpenShift's
seccomp profiles refuse it, and on an SELinux host podman's container label refuses a mount
it needs. So the image names its own `devagent-bwrap` as Claude Code's
`sandbox.bwrapPath`. Per command, it runs the **real bubblewrap** where it can start and
otherwise **landrun + proot**: Landlock for what may be read, written and executed, and
ptrace path rewriting for the masked files and empty directories Landlock cannot express.

| | real bubblewrap (an ordinary Linux host) | landrun + proot (podman, docker, OpenShift workspaces) |
|---|---|---|
| Write confinement | kernel mount namespace | kernel (Landlock) |
| Masked files, empty directories, read-only paths inside writable ones | kernel mounts | **path rewriting** (proot): enforced for every normal program, but not a kernel boundary |
| Unix-socket block | Claude's seccomp helper | an equivalent seccomp filter |
| Processes | private PID namespace: other processes invisible, everything dies with the command | **shared**: other processes are visible (not their memory or environment). A keeper kills the command's process group when it ends |
| Network | private namespace with its own loopback; TCP only through Claude's proxy | **open by default** (§1.5); optionally TCP only through the proxy, with no loopback |
| UDP | private | **not confined** |
| Parallel sandboxes | each has its own loopback | **one shared loopback**: two test servers on the same fixed port collide |
| Overhead per command | milliseconds | about **120 ms** to start (*measured*, OpenShift), and ptrace on every intercepted syscall: `find /usr -type f` took 0.72 s against 0.27 s unsandboxed; compute-bound work loses only the start-up |

What this means for an agent: **treat masks as a strong convention, not a wall**, do not
rely on process isolation between sandboxed commands, and pick random ports (port 0) for
test servers when sub-agents run in parallel.

### 1.5 The network, and what turning its isolation on costs

On landrun + proot the sandbox's network part is **off by default**: a sandboxed command
has the container's network. Local servers, test databases and dev servers work. Claude's
proxy variables are still set, so tools that honour `HTTP(S)_PROXY` still go through its
proxy and its domain allowlist, but a tool that ignores them, or a command that means to,
can reach any host directly.

**To turn it on**, set `DEVAGENT_BWRAP_NETWORK=restrict` in the agent's environment. The
simplest place is Claude's settings, which reach the shim (*measured*):

```json
{ "env": { "DEVAGENT_BWRAP_NETWORK": "restrict" } }
```

Then TCP from a sandboxed command goes only to Claude's proxy, and the allowlist holds.
**The cost:** Landlock can allow TCP by port only, never by address, so there is no
loopback either. **Any command that starts a local server and connects to it fails**
(`EACCES` on `bind` or `connect`): most integration-test suites, `npm run dev` plus a
browser check, a local Postgres. Claude may then offer to rerun it unsandboxed; with
`allowUnsandboxedCommands: false` it cannot. A value other than `open` or `restrict` is
refused, so a typo cannot leave the network open by accident. Where the real bubblewrap
runs, its private network is always on and none of this applies.

Other switches, set the same way:

| Variable | Values | Effect |
|---|---|---|
| `DEVAGENT_BWRAP_NETWORK` | `open` (default), `restrict` | as above |
| `DEVAGENT_BWRAP_SHIM` | `1` (default), `0`, `2` | `0`: always the real bubblewrap (which cannot start in most workspaces, §1.4); `2`: always landrun + proot |

### 1.6 Rules for an agent

1. Do not assume the sandbox is on. If isolation of a sub-agent matters, check the
   settings, or run `devagent-bwrap --devagent-tier ...` (§1.3).
2. Keep sub-agents away from files with **both**: the sandbox for their shell, and
   `permissions.deny` for their file tools.
3. With the network restricted, run tests that need a local server unsandboxed only with
   the user's approval, and say why.
4. Give parallel sub-agents distinct, preferably kernel-chosen, ports.
5. Do not write secrets anywhere a sandboxed command can read: reads are open by default.

---

## 2. Memory: the container has a limit, and crossing it kills work

Everything in this section is read **from inside the container**, which is where the
agent is. Nothing here needs, or assumes, access to the cluster, the runtime or the host.

### 2.1 What happens at the limit

A workspace container may have a memory limit. When the processes in it together exceed
it, the kernel's OOM killer kills, and what it kills depends on how the container was
started (*measured*; the container says which, in `memory.oom.group`, §2.3):

| `memory.oom.group` | What an OOM kills | What the agent sees afterwards |
|---|---|---|
| `1` (a Kubernetes or OpenShift pod) | **every process in the container**, and the container is restarted: the agent, its sub-agents, tmux sessions, background jobs, `nohup` and `setsid` alike | a new container: a young PID 1 (§2.3), empty cgroup counters, and only the files on its volumes (and, after an in-place restart, in an `emptyDir` `/tmp`). devagent restores the agent session and nudges it to continue, but in-flight work is gone |
| `0` (podman or docker with a limit) | **one process**, usually the largest, which may be the agent itself or a worker it started | the container carries on; `oom_kill` in `memory.events` has grown |

Either way an agent that relaunches the same work unchanged is killed again. This has
happened (*measured*, [SUBAGENT.md](SUBAGENT.md), the cap-evolve incident): six restarts in
25 minutes, each after a relaunch of a 24-worker job. The agent concluded, wrongly, that
"the session ending" killed its processes.

### 2.2 The limit is not a known number: detect it

The limit is chosen **per workspace, when it is created**, and differs from one workspace
to the next. A container on podman or docker usually has none of its own. Do not assume
any value, and do not take it from anything but the container's own cgroup:

* **`free`, `top` and `/proc/meminfo` do not show the limit.** They show the host's or
  the node's memory (*measured*: 64 GB on a laptop, 774 GB on an OpenShift node, for
  containers limited to 1 GiB and 8 GiB). Budgeting from them is how a container gets
  OOM-killed with "plenty of memory free".
* **`nproc` does not show the CPU limit either** (*measured*: 96 on a pod limited to 4
  CPUs). Size worker pools from `cpu.max` and from memory, never from `nproc`.
* When the cgroup says there is **no limit** (`memory.max` is `max`), the container can
  use the host's memory, shared with everything else there. Then `MemAvailable` in
  `/proc/meminfo` is the honest headroom, and the host's OOM killer may pick any process,
  inside the container or not.
* If `memory.high` is set below `memory.max`, the kernel starts throttling the container
  there, so that is the limit to budget against.
* Swap differs too (*measured*: none on OpenShift; podman's `--memory 1g` also allows 1 GiB
  of swap). Do not count swap as headroom: at best it is a slowdown before the kill.

### 2.3 How to read it: `memcheck`

Save this as `~/bin/memcheck` (or run it inline). It reads only the container's own
cgroup and `/proc`, and prints one `key=value` per line:

```sh
#!/bin/sh
# memcheck: this container's memory and CPU, from the inside (CONTAINER_AGENT.md §2).
# Usage: memcheck [per_subagent_MB]   (default 750)
per=${1:-750}
cg=/sys/fs/cgroup
mb() { echo $(( $1 / 1048576 )); }
if [ -f $cg/memory.max ]; then                      # cgroup v2: every container measured
    lim=$(cat $cg/memory.max)
    high=$(cat $cg/memory.high 2>/dev/null || echo max)
    if [ "$high" != max ] && { [ "$lim" = max ] || [ "$high" -lt "$lim" ]; }; then lim=$high; fi
    cur=$(cat $cg/memory.current)
    used=$(awk '$1=="anon"||$1=="shmem"{s+=$2} END{print s+0}' $cg/memory.stat)
    peak=$(cat $cg/memory.peak 2>/dev/null || echo 0)
    ooms=$(awk '$1=="oom_kill"{print $2}' $cg/memory.events)
    group=$(cat $cg/memory.oom.group 2>/dev/null || echo 0)
    swap=$(cat $cg/memory.swap.max 2>/dev/null || echo 0)
    set -- $(cat $cg/cpu.max 2>/dev/null || echo max)
    if [ "$1" = max ]; then cpus=none; else cpus=$(( ($1 + $2 - 1) / $2 )); fi
elif [ -f $cg/memory/memory.limit_in_bytes ]; then  # cgroup v1 (older hosts; not measured)
    lim=$(cat $cg/memory/memory.limit_in_bytes)
    [ "$lim" -ge 4611686018427387904 ] && lim=max
    cur=$(cat $cg/memory/memory.usage_in_bytes)
    used=$(awk '$1=="total_rss"||$1=="total_shmem"{s+=$2} END{print s+0}' $cg/memory/memory.stat)
    peak=$(cat $cg/memory/memory.max_usage_in_bytes)
    ooms=$(awk '$1=="oom_kill"{print $2}' $cg/memory/memory.oom_control)
    group=unknown swap=unknown cpus=unknown
else
    echo "verdict=UNKNOWN (no cgroup memory files here)"; exit 2
fi
age=$(( $(cut -d. -f1 /proc/uptime) - $(awk '{print $22}' /proc/1/stat) / $(getconf CLK_TCK) ))
echo "container_age_s=$age"
echo "cpu_limit=$cpus"
echo "used_MB=$(mb $used)  current_MB=$(mb $cur)  peak_MB=$(mb $peak)"
echo "oom_kills_since_start=$ooms  oom_kills_whole_container=$group  swap_max=$swap"
if [ "$lim" = max ]; then
    avail=$(( $(awk '/^MemAvailable/{print $2}' /proc/meminfo) * 1024 ))
    echo "limit_MB=none (host memory, shared; MemAvailable_MB=$(mb $avail))"
    room=$(( avail / 2 ))                           # leave half of a shared host to others
else
    echo "limit_MB=$(mb $lim)  used_pct=$(( used * 100 / lim ))"
    room=$(( lim * 75 / 100 - used ))
fi
fit=$(( room / (per * 1048576) )); [ $fit -lt 0 ] && fit=0
if [ "$lim" != max ] && [ $(( used * 100 / lim )) -ge 85 ]; then v=STOP
elif [ "$lim" != max ] && [ $(( used * 100 / lim )) -ge 75 ]; then v=CAUTION
else v=OK; fi
echo "verdict=$v  subagents_that_fit=$fit (at ${per} MB each, before what they run)"
```

`used` is anonymous memory plus `shmem` (tmpfs), which the kernel cannot reclaim without
swap; `current` adds the page cache, which it drops before it kills anything, so a large
`current` with a small `used` is not a problem. `container_age_s` is how long PID 1 has
run: the one way, from inside, to tell that the container restarted.

*Measured*, the script exactly as above:

| Container | What `memcheck` said |
|---|---|
| podman, no limit | `limit_MB=none (host memory, shared; MemAvailable_MB=31501)`, `cpu_limit=none` |
| podman `--memory 4g --cpus 2` | `limit_MB=4096`, `cpu_limit=2`, `swap_max=4294967296`, `subagents_that_fit=4` |
| docker `--memory 2g` | `limit_MB=2048`, `oom_kills_whole_container=0` |
| an OpenShift workspace in use | `limit_MB=8192 used_pct=14`, `cpu_limit=4`, `swap_max=0`, `oom_kills_whole_container=1`, `container_age_s=333418`, `subagents_that_fit=6` |
| podman `--memory 256m`, 230 MB allocated | `used_pct=91 verdict=STOP subagents_that_fit=0`; after a 400 MB allocation was killed (exit 137), `oom_kills_since_start=2` and the container lived |

### 2.4 What a sub-agent costs

Sub-agents run inside the parent's Claude Code process, so each one grows that process,
and every command it runs adds its own processes on top. *Measured* on OpenShift
workspaces (TOOLING.md §9.13):

| What | Memory |
|---|---|
| An idle workspace container | `memory.current` 2.1 GB, of which **18 MB** is `used` (anonymous): the rest is page cache, reclaimable |
| One `claude -p` turn (CLI process) | peak RSS **262 MB** |
| The same turn with 1, then 3 parallel sub-agents that only read files | peak RSS 262 and 263 MB: a light sub-agent adds almost nothing by itself |
| A long-lived Claude Code session (VS Code panel), in two real workspaces | **215 to 257 MB** per CLI process |
| Each MCP server a session starts (Playwright, as `npx`) | about **200 MB** (`playwright-mcp` 110 MB + `npm exec` 88 MB), per session |
| VS Code server processes | 100 to 300 MB each |
| A workspace running worker pools (`cap-evolve-infra`) | a high-water mark (`memory.peak`) of **86% of its limit**; *inferred* to be the pools, since its agent processes were 235 to 260 MB |

So what a sub-agent costs is mostly **what it runs**: its context grows with long work, and
its commands (a compiler, a test runner, a worker pool, a browser) can take gigabytes. For
planning, budget **750 MB per sub-agent** before its commands, which is `memcheck`'s
default: conservative for a sub-agent that only reads and edits, still too little for one
that builds or tests. The rules below measure rather than trust the budget.

### 2.5 Rules for an agent

1. **Run `memcheck` before you spawn.** Before launching sub-agents or parallel jobs, start
   no more than `subagents_that_fit`, less what their commands will need. Do not spawn on
   `CAUTION` or `STOP`.
2. **Run it while you work.** During long parallel work, every few minutes and whenever a
   sub-agent or job starts. On `CAUTION` (75% of the detected limit), start nothing new; on
   `STOP` (85%), stop or shrink what you started, most recent first: fewer workers, smaller
   batches.
3. **Size worker pools from `cpu_limit` and from memory**, never from `nproc`: `-j`,
   `--workers`, pytest-xdist `-n`, and the like. A pool of `nproc` workers on a large node
   is dozens of processes in a container that may hold a few.
4. **After a restart, find out why before relaunching.** If `container_age_s` is shorter
   than your session, the container restarted. With `oom_kills_whole_container=1` its
   counters were reset by that restart, so they cannot tell you it was an OOM: treat the
   work you launched just before as the suspect, and relaunch it smaller, never unchanged.
   With `0`, a grown `oom_kills_since_start` means a single process was killed and the
   container lived: find which (`dmesg` is usually not readable in a container; look for
   the job that vanished).
5. **Prefer sequential sub-agents** when their work is large, and keep sub-agent prompts
   from spawning further sub-agents.
6. **Tell the user when the work needs more than the container has.** The limit is set
   when a workspace is created; a larger one is their decision, not something to work
   around.
