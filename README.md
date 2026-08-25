# RacingAnalyzer

GT7 遥测采集、圈速分析和驾驶诊断工具。项目保留 `gt7` 作为兼容命令，同时提供 `racing-analyzer` 入口。

## 当前架构

```text
PS5 192.168.50.246:33739
        ↓ UDP
当前服务器 192.168.50.20:33740
  watcher / 状态识别 / SQLite / 圈速与赛道分析
        ↓ SSH + rsync
VM102 192.168.50.13
  开发代码 / 原始 capture 归档 / SQLite 快照 / 离线实验
```

SQLite 不直接运行在网络共享上。当前服务器本地实时写入，归档服务使用 SQLite 原生 backup 创建一致性快照后再同步到 VM102。原始 capture 不会因分析失败自动删除。

## 开发与验证

在 VM102 开发环境执行：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
pytest -q
python -m compileall -q src tests
```

开发目录：`/home/amaranth/code/original/gt7-coach`

当前服务器运行目录：`/home/amaranth/services/gt7-coach`

## 当前服务器运行

systemd user units：

```text
gt7-coach-watcher.service
gt7-coach-archive.timer
```

watcher 常驻监听 UDP `33740`，GT7 暂时退出、菜单或无包时不主动结束；异常退出由 systemd 自动重启。归档 timer 将 capture 和一致性 SQLite 快照同步到 VM102 的 `~/archives/gt7-coach`。

## CLI

两个入口等价：

```bash
.venv/bin/racing-analyzer --help
.venv/bin/gt7 --help
```

查看 session 和合法完整圈边界：

```bash
.venv/bin/racing-analyzer --db data/gt7.sqlite3 summary --session 5
```

分析最近一个合法完整圈：

```bash
.venv/bin/racing-analyzer --db data/gt7.sqlite3 analyze \
  --session 5 --track tracks/nurburgring_nordschleife.json
```

比较同一 session 内的完整圈：

```bash
.venv/bin/racing-analyzer --db data/gt7.sqlite3 compare --session 5
```

比较不同 session 的最近合法完整圈：

```bash
.venv/bin/racing-analyzer --db data/gt7.sqlite3 compare \
  --sessions 1 5 --segment-m 200
```

跨 session 比较输出最佳/最慢 session、圈速差值、相对百分比和固定距离 micro-sector 赢家。当前纽北映射仍为 `uncalibrated`，未校准前只输出距离区间或 `micro-sector-N`，不假称具体弯道名称。

手动导入原始 capture：

```bash
.venv/bin/racing-analyzer --db data/gt7.sqlite3 import data/captures/<capture>.bin
```

## 真实数据基线

当前已验证两条独立有效圈：

```text
7:19.208  session 1  开始：2026-08-24 21:36:28.337（北京时间）
7:23.413  session 5  开始：2026-08-25 23:00:15.021（北京时间）
```

两份数据解密错误均为 0。session 2、3 是 session 1 同一原始 capture 的重复导入，不作为独立驾驶样本。
