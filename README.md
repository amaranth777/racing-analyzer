# RacingAnalyzer

GT7 遥测采集、圈速分析和驾驶诊断工具。项目保留 `gt7` 作为兼容命令，同时提供 `racing-analyzer` 入口。

## 当前架构

```text
PS5 192.168.50.246:33739
        ↓ UDP
生产服务器 192.168.50.20:33740
  watcher / 状态识别 / SQLite / 圈速与赛道分析
  生产运行目录与本地归档（均不离开服务器）

VM102 192.168.50.13
  只用于开发、测试和离线实验；不运行生产 watcher
```

生产数据只在服务器运行：服务器本地实时写入 SQLite 和 `captures`，归档也由服务器本地脚本完成。归档脚本使用 SQLite 原生 `backup()` 创建一致性快照，再把 captures 复制到服务器本地归档目录；它不通过网络、SSH 或 VM102 写入，也不会删除源数据。VM102 不保存生产运行数据或归档。

服务器上的 systemd（或手动任务）必须显式传入两个本地目录，例如：

```bash
.venv/bin/python scripts/archive_runtime.py \
  --runtime-dir /home/amaranth/.local/share/racinganalyzer/data \
  --archive-dir /home/amaranth/.local/share/racinganalyzer/archive
```

RacingAnalyzer 只生成确定性的高阶证据：合法圈边界、去重结果、圈速/分段差异、控制指标、事件、轮速诊断和数据质量。它不生成最终驾驶建议；Hermes 读取这些证据后，结合历史圈、车辆/赛道和用户目标，由大模型负责归因、排序和输出训练建议。

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

## Hermes Skill

仓库内置 `skills/racing-analyzer/SKILL.md`，用于让 Hermes/大模型快速掌握 Analyzer 的调用方式、JSON 证据契约、去重语义和置信度边界。Hermes 默认只从当前 profile 的 `$HERMES_HOME/skills/` 加载 Skill，不会扫描任意项目目录；因此首次使用时显式安装到当前 profile：

```bash
python3 scripts/install-hermes-skill.py --check
python3 scripts/install-hermes-skill.py
```

安装器默认拒绝覆盖已有的不同版本；确认更新来源后使用 `--force`。安装后新 Hermes 会话即可按任务自动匹配 `racing-analyzer` Skill。Skill 只教模型读取确定性证据，不让 Analyzer 生成最终驾驶建议；归因、排序和训练建议由 Hermes 完成。

## 当前服务器运行

systemd user units：

```text
gt7-coach-watcher.service
gt7-coach-archive.timer
```

watcher 常驻监听 UDP `33740`，GT7 暂时退出、菜单或无包时不主动结束；异常退出由 systemd 自动重启。归档任务在生产服务器本地执行，把一致性 SQLite 快照写入服务器的 archive 目录，并把 captures 复制到其 `captures/` 子目录；不向 VM102 或其他网络目标写入。

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

跨 session 比较输出最佳/最慢 session、圈速差值、相对百分比、重复 session 和固定距离 micro-sector 赢家。`analyze` 输出供 Hermes 使用的确定性证据，不直接输出自然语言建议。当前纽北映射仍为 `uncalibrated`，未校准前只输出距离区间或 `micro-sector-N`，不假称具体弯道名称。

检查最近 session 的数据质量（质量失败返回退出码 2）：

```bash
.venv/bin/racing-analyzer --db data/gt7.sqlite3 validate
# quality 是同一命令的别名；可显式指定 session
.venv/bin/racing-analyzer --db data/gt7.sqlite3 quality --session 5
```

检查失败时可写入幂等 quarantine manifest；该选项只记录 session 和 issue，不移动或删除 SQLite/capture 源数据：

```bash
.venv/bin/racing-analyzer --db data/gt7.sqlite3 validate \
  --session 5 --quarantine data/quarantine.json
```

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
