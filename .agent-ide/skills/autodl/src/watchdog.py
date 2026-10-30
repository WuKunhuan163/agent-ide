"""后台看门狗：实例上没有任务在跑，就把它关掉。

它**不是**「检测到断连就关机」。三件事实决定了这个区别：

1. 容器不能自我关机，`poweroff` 只停进程，计费照走；
2. SSH 断连对容器不可见，它眼里一切正常；
3. `nohup` 的任务在断连后本来就该继续跑——断连关机等于第一次网络抖动就杀掉长任务。

真正要防的场景是：我这边停了（会话结束、Mac 睡了），而机器还开着。所以判据是
「有没有任务在跑」，不是「有没有连接」。

**不认进程名。** 早先的探测是 `pgrep` 找 `run.py|train.py`，那等于维护一张名单：
换个脚本名、套层 `torchrun`、跑在没有 GPU 的 CPU 机上，都会被判成「闲着」。
现在的判据是三个物理量：`nvidia-smi` 的算力进程数与最高利用率、`/proc/loadavg`
的一分钟负载、`/root/autodl-tmp` 的写盘时间。跟脚本叫什么无关，CPU 模式也成立。

连续 `rounds` 次判闲才真正 `stop`，避免训练在两个 epoch 之间的正常间隙里被关掉。
网络不通时**不推进计数**：宁可多花一小时的钱，也不误杀一个跑了一半的任务。

**开机即挂，等它真起来再开始数。** `power_on` 之后实例要先经过
`starting`/`booting` 才到 `running`，早先的实现一看到不是 `running` 就退出，
于是看门狗在真正开始追踪之前就已经死了。现在先等（`boot_grace_seconds`），
起来之后才进入计数循环；只有「已经 running 过又变成 shutdown」才算结束。

配置一律在 `data/config.json` 的 `watchdog` 段里，不读任何环境变量。
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import client  # noqa: E402
from src.client import AUTH, NET, NO_TOKEN, OK, SSH, USAGE, CliError  # noqa: E402

DEFAULTS = {
    "interval_seconds": 60,      # 起来之后每分钟看一次
    "idle_minutes": 1,           # 这一分钟内有过写盘就算在用
    "rounds": 30,                # 连续 30 次判闲才关机（60s × 30 = 30 分钟）
    "boot_grace_seconds": 900,   # 等实例从 shutdown 走到 running 的上限
    "gpu_util_min": 10,          # 最高一张卡的利用率到这个数就算在用（%）
    "cpu_load_min": 1,           # 一分钟负载到这个数就算在用（CPU 模式的判据）
}
PROBE_MARK = "---AUTODL---"
PROBE_TIMEOUT = 60
BOOT_POLL_SECONDS = 15          # 起来之前勤快点问，起来之后按 interval 走
# token 失效这类错误重试也没有意义，但一次失败可能只是抖动：连续这么多次才放弃。
MAX_BLIND_TICKS = 12


# --------------------------------------------------------------------------- 配置与状态

def state_file() -> str:
    return os.path.join(client.data_dir(), "watchdog.json")


def log_file() -> str:
    return os.path.join(client.data_dir(), "watchdog.log")


def settings() -> dict:
    """`data/config.json` 的 watchdog 段，缺的键用默认值补齐。"""
    merged = dict(DEFAULTS)
    try:
        with open(client.config_file(), encoding="utf-8") as fh:
            raw = json.load(fh)
    except (OSError, ValueError):
        raw = {}
    section = raw.get("watchdog") if isinstance(raw, dict) else None
    if isinstance(section, dict):
        for key in DEFAULTS:
            if isinstance(section.get(key), int) and section[key] > 0:
                merged[key] = section[key]
    return merged


def read_state() -> dict | None:
    try:
        with open(state_file(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_state(state: dict) -> None:
    path = state_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def drop_state() -> None:
    try:
        os.remove(state_file())
    except OSError:
        pass


def alive(pid: int) -> bool:
    if not isinstance(pid, int) or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def log(line: str) -> None:
    path = log_file()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(f"{stamp} {line}\n")


# --------------------------------------------------------------------------- 判据（纯函数）

@dataclass(frozen=True)
class Decision:
    action: str  # exit | hold | idle | stop
    streak: int
    reason: str


@dataclass(frozen=True)
class Usage:
    """一次探测看到的用量。三项都跟进程名无关，所以换脚本、套 torchrun、纯 CPU 都成立。"""
    load: float      # /proc/loadavg 的一分钟值
    apps: int        # nvidia-smi 里占着卡的计算进程数
    util: float      # 所有卡里最高的利用率（%）
    touched: bool    # idle 窗口内 /root/autodl-tmp 有新文件


def busy(usage: Usage, *, util_min: int, load_min: int) -> str | None:
    """在用就返回理由，闲着返回 None。"""
    if usage.apps:
        return f"{usage.apps} process(es) on the GPU"
    if usage.util >= util_min:
        return f"GPU at {usage.util:.0f}%"
    if usage.load >= load_min:
        return f"load {usage.load:.2f}"
    if usage.touched:
        return "files written inside the idle window"
    return None


def decide(usage: Usage, *, streak: int, rounds: int, util_min: int, load_min: int) -> Decision:
    """一轮探测之后该做什么。不联网，便于测试。streak 是之前连续判闲的次数。"""
    why = busy(usage, util_min=util_min, load_min=load_min)
    if why:
        return Decision("idle", 0, why)
    streak += 1
    if streak >= rounds:
        return Decision("stop", streak, f"idle on {streak} consecutive checks")
    return Decision("idle", streak, f"idle {streak}/{rounds}")


def parse_probe(text: str) -> Usage:
    """解析探测输出：`键 值` 三行，PROBE_MARK 之后是写盘命中。

    缺 nvidia-smi（CPU 模式的机器）时 apps/util 保持 0，判据自动落到负载和写盘上。
    """
    head, _, tail = text.partition(PROBE_MARK)
    load, apps, util = 0.0, 0, 0.0
    for line in head.splitlines():
        key, _, value = line.strip().partition(" ")
        value = value.strip().replace(" ", "")
        try:
            if key == "load":
                load = float(value or 0)
            elif key == "apps":
                apps = int(value or 0)
            elif key == "util":
                for part in value.split(","):
                    util = max(util, float(part))  # [N/A] 之类会被下面的 except 跳过
        except ValueError:
            continue
    return Usage(load=load, apps=apps, util=util, touched=bool(tail.strip()))


def probe_command(idle_minutes: int) -> str:
    return (
        'bash -lc \''
        'echo "load $(cut -d" " -f1 /proc/loadavg)"; '
        'echo "apps $(nvidia-smi --query-compute-apps=pid --format=csv,noheader '
        '2>/dev/null | grep -c "[0-9]")"; '
        'echo "util $(nvidia-smi --query-gpu=utilization.gpu --format=csv,noheader,nounits '
        '2>/dev/null | tr -d " " | paste -sd, -)"; '
        f"echo {PROBE_MARK}; "
        f"find /root/autodl-tmp -maxdepth 4 -type f -mmin -{idle_minutes} "
        "2>/dev/null | head -3'"
    )


# --------------------------------------------------------------------------- 远端

def remote_exec(uuid: str, command: str, api: "client.Client") -> tuple[int, str]:
    """跑一条远端命令，返回 (退出码, 输出)。返回码 255 表示 ssh 本身失败。"""
    data = api.call("GET", client.SNAPSHOT, {"instance_uuid": uuid})
    if not isinstance(data, dict):
        raise CliError(client.API, f"snapshot for {uuid} came back empty")
    host, port, password = data.get("proxy_host"), data.get("ssh_port"), data.get("root_password")
    if not host or not port or not password:
        raise CliError(client.API, f"snapshot for {uuid} carried no ssh endpoint")
    sshpass = shutil.which("sshpass")
    if not sshpass:
        raise CliError(SSH, "no non-interactive ssh: install sshpass, or let the box idle off by hand")
    argv = [sshpass, "-p", str(password), "ssh", "-p", str(port),
            "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=15",
            f"root@{host}", command]
    try:
        done = subprocess.run(argv, capture_output=True, text=True, timeout=PROBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return 255, ""
    return done.returncode, (done.stdout or "") + (done.stderr or "")


# --------------------------------------------------------------------------- 一轮

def wait_for_running(uuid: str, api: "client.Client", grace: int) -> str | None:
    """等实例真的跑到 running。返回 None 表示起来了，否则返回放弃的理由。

    `power_on` 被接受 ≠ 已经 running：中间还有 starting/booting。早先的 tick 把
    「不是 running」当成结束，于是 start 刚挂上的看门狗立刻自己退了。
    """
    start = time.time()
    while True:
        try:
            state = str(api.call("GET", client.STATUS, {"instance_uuid": uuid})).strip()
        except CliError as exc:
            log(f"waiting for {uuid}: {exc}")
            state = ""
        if state == "running":
            return None
        if state == "shutdown" and time.time() - start > 60:
            # 开机一分钟了还是 shutdown：多半是这次开机被取消或失败了，别空等
            return f"still {state} one minute after power_on"
        if time.time() >= start + grace:
            # 先问再判超时：最后一次轮询不该被丢掉
            return f"not running within {grace}s"
        time.sleep(BOOT_POLL_SECONDS)


def tick(uuid: str, cfg: dict, streak: int, api: "client.Client") -> Decision:
    state = api.call("GET", client.STATUS, {"instance_uuid": uuid})
    if str(state).strip() != "running":
        return Decision("exit", streak, f"instance is {state}")

    code, text = remote_exec(uuid, probe_command(cfg["idle_minutes"]), api)
    if code != 0:
        return Decision("hold", streak, f"probe failed (ssh exit {code}); not counting this round")

    return decide(parse_probe(text), streak=streak, rounds=cfg["rounds"],
                  util_min=cfg["gpu_util_min"], load_min=cfg["cpu_load_min"])


def run_foreground(uuid: str, cfg: dict) -> int:
    try:
        api = client.Client(client.load()["tokens"])   # 按 host 取槽：实例都在 Pro 那朵云
    except CliError as exc:
        log(f"cannot start: {exc}")
        return getattr(exc, "code", client.FAILED)
    streak, blind = 0, 0
    write_state({"uuid": uuid, "pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                 "phase": "booting", **cfg})
    log(f"start uuid={uuid} interval={cfg['interval_seconds']}s "
        f"idle={cfg['idle_minutes']}min rounds={cfg['rounds']} "
        f"util>={cfg['gpu_util_min']}% load>={cfg['cpu_load_min']}")

    def _bye(signum, _frame):
        log(f"signal {signum}: stopping the watchdog, not the instance")
        drop_state()
        raise SystemExit(OK)

    signal.signal(signal.SIGTERM, _bye)
    signal.signal(signal.SIGINT, _bye)

    try:
        reason = wait_for_running(uuid, api, cfg["boot_grace_seconds"])
        if reason:
            log(f"exit before watching: {reason}")
            return OK
        log("running; watching usage")
        write_state({"uuid": uuid, "pid": os.getpid(), "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "phase": "watching", **cfg})

        while True:
            try:
                verdict = tick(uuid, cfg, streak, api)
            except CliError as exc:
                code = getattr(exc, "code", client.FAILED)
                if code == NET:
                    blind += 1
                    log(f"network down (attempt {blind}): will retry, streak stays at {streak}")
                    time.sleep(cfg["interval_seconds"])
                    continue
                if code == SSH:
                    log(f"no way to probe the box ({exc}); it can never see a job, exiting")
                    return code
                if code in (AUTH, NO_TOKEN):
                    log(f"cannot authenticate ({exc}); the watchdog cannot stop anything, exiting")
                    return code
                blind += 1
                log(f"tick failed ({exc}); attempt {blind}")
                if blind >= MAX_BLIND_TICKS:
                    log("too many failures in a row, exiting without stopping the instance")
                    return client.FAILED
                time.sleep(cfg["interval_seconds"])
                continue

            blind = 0
            if verdict.action == "exit":
                log(f"exit: {verdict.reason}")
                return OK
            if verdict.action == "stop":
                log(f"stop: {verdict.reason}; calling power_off")
                api.call("POST", client.POWER_OFF, {"instance_uuid": uuid})
                log("stopped; billing ends here")
                return OK

            log(f"tick {verdict.reason}")
            streak = verdict.streak
            time.sleep(cfg["interval_seconds"])
    finally:
        drop_state()


# --------------------------------------------------------------------------- 前后台

def spawn_in_background(uuid: str, cfg: dict | None = None) -> int:
    """拉起一个脱离当前会话的看门狗；已在跑就不重复起。返回 pid，未启动返回 0。"""
    current = read_state()
    if current and current.get("uuid") == uuid and alive(int(current.get("pid", 0))):
        return int(current["pid"])
    if current and alive(int(current.get("pid", 0))):
        return 0  # 另一个实例的看门狗还在跑；单容器纪律下这是不应发生的事

    cfg = {**DEFAULTS, **(cfg or settings())}
    os.makedirs(client.data_dir(), exist_ok=True)
    with open(log_file(), "a", encoding="utf-8") as sink:
        proc = subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), uuid, "--foreground",
             "--interval", str(cfg["interval_seconds"]),
             "--idle", str(cfg["idle_minutes"]),
             "--rounds", str(cfg["rounds"])],
            cwd=ROOT, stdin=subprocess.DEVNULL, stdout=sink, stderr=sink,
            start_new_session=True, close_fds=True,
        )
    return proc.pid


def status_line() -> str:
    current = read_state()
    if not current:
        return "stopped"
    if not alive(int(current.get("pid", 0))):
        return f"stale pid={current.get('pid')} uuid={current.get('uuid')}"
    return (f"running pid={current.get('pid')} uuid={current.get('uuid')} "
            f"since={current.get('started')} idle={current.get('idle_minutes')}min "
            f"rounds={current.get('rounds')}")


def stop_watchdog() -> int:
    current = read_state()
    if not current or not alive(int(current.get("pid", 0))):
        drop_state()
        return 0
    pid = int(current["pid"])
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    for _ in range(20):
        if not alive(pid):
            break
        time.sleep(0.1)
    drop_state()
    log(f"watchdog pid={pid} stopped by request")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        print('usage: watchdog <uuid> [--foreground] | --status | --off', file=sys.stderr)
        return USAGE
    if argv[0] == "--status":
        print(status_line())
        return OK
    if argv[0] == "--off":
        return stop_watchdog()

    uuid = argv[0]
    cfg = settings()
    flags = {"--interval": "interval_seconds", "--idle": "idle_minutes", "--rounds": "rounds"}
    for i, token in enumerate(argv[:-1]):
        key = flags.get(token)
        if key and argv[i + 1].isdigit() and int(argv[i + 1]) > 0:
            cfg[key] = int(argv[i + 1])

    if "--foreground" in argv[1:]:
        return run_foreground(uuid, cfg)
    pid = spawn_in_background(uuid, cfg)
    print(pid if pid else "already running")
    return OK


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
