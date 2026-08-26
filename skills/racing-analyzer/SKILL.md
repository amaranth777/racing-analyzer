---
name: racing-analyzer
description: Use RacingAnalyzer to inspect GT7 telemetry evidence.
version: 0.1.0
author: amaranth777, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [GT7, telemetry, racing, lap-analysis, driving]
    related_skills: []
---

# RacingAnalyzer Skill

Use RacingAnalyzer as the deterministic evidence layer for GT7 telemetry. It calculates lap boundaries, duplicate identity, lap and sector metrics, control signals, events, wheel diagnostics, and data-quality facts. It does not produce the final driving advice: Hermes combines this evidence with the user's goal, history, car, and track context, then asks the model to explain, prioritize, and recommend.

## When to Use

Use this skill when the user asks to:

- inspect a GT7 session or a completed lap;
- compare laps or sessions;
- find repeated imports or independent driving samples;
- identify measurable control, braking, throttle, steering, or wheel anomalies;
- prepare telemetry evidence for a coaching response.

Do not treat menu time, an out-lap, an aborted attempt, a short no-packet interval, or a wheel anomaly by itself as proof of driving behavior.

## Prerequisites

- RacingAnalyzer is installed and its SQLite database path is known.
- Use the project's `racing-analyzer` entry point; keep the database and raw captures local to the analyzer host.
- Do not upload raw telemetry, SQLite files, credentials, or private paths to an external model.

If the Skill is installed under the active Hermes profile, resolve the repository/runtime location from the user's environment; never assume a fixed home directory. The active profile home is `$HERMES_HOME` when set; otherwise use the user's normal Hermes home.

## Quick Reference

Run commands through the `terminal` tool. The JSON on stdout is the analyzer evidence payload.

```python
terminal(command="racing-analyzer --db <db> summary --session <id>")
terminal(command="racing-analyzer --db <db> analyze --session <id> --segment-m 200")
terminal(command="racing-analyzer --db <db> compare --sessions <id> <id> --segment-m 200")
```

For the current production layout, the executable and database may be under the service directory; inspect the service's documented runtime path instead of inventing one.

## Procedure

1. Establish the scope: identify the requested session IDs, car, track, and comparison goal.
2. Run `summary` when the session identity or lap boundary is uncertain.
3. Run `analyze` for one session's last complete positive lap. Preserve its JSON evidence.
4. Run `compare --sessions` for cross-session comparison. Include every candidate session so duplicate imports can be reported.
5. Check the data-quality facts before interpreting behavior: decode errors, complete-lap boundaries, frame coverage, and whether the result is a canonical or duplicate sample.
6. Feed the compact evidence—not raw frames—to Hermes's reasoning layer. Ask the model to distinguish observation, hypothesis, and recommendation.
7. State uncertainty explicitly. A suspected wheel event requires replay or visual confirmation before being called a confirmed mistake.

## Evidence Contract

`analyze` returns deterministic evidence such as:

- `session_id`, `lap`, `lap_time_s`, `start_seq`, `end_seq`, `start_ts_ns`, `end_ts_ns`;
- `distance_m`, `segment_m`, `segment_count`, and `segments`;
- `slowest_segments` as a compact ranking of segment observations;
- `control_metrics`, including sample count, brake/throttle overlap with steering, and steering reversals;
- `events`, with type, distance range, duration, and observed speed facts;
- `wheel_events`, deliberately marked with `confidence: "suspected"`;
- no final `recommendations` field. Natural-language advice belongs to Hermes.

`compare --sessions` returns canonical lap records plus:

- `duplicate_session_ids`;
- `deduplicated_count`;
- `best_session_id`, `slowest_session_id`, `delta_s`, and `delta_pct`;
- deterministic fixed-distance segment winners.

A duplicate means the complete legal lap has the same vehicle, lap time, relative timing, and telemetry sequence while ignoring import/session identity and absolute timestamp origin. Equal lap time alone is not a duplicate.

## Analyzer/Hermes Boundary

Analyzer may calculate facts, aggregates, rankings, intervals, confidence labels, and comparisons. Analyzer must not invent causes such as "missed the apex" from telemetry alone, prescribe a training plan, or emit the final natural-language coaching advice.

Hermes should:

- cite the relevant distance/segment and measured value;
- separate confirmed observation from plausible cause;
- rank only a small number of high-impact issues;
- account for the user's stated goal and prior laps;
- turn evidence into concrete practice advice;
- avoid treating `confidence: "suspected"` as confirmed.

A good response shape is: measured evidence → likely interpretations → prioritized recommendation → one practice drill → what to verify on the next lap.

## Pitfalls

- Do not count repeated `last_lap_ms` frames as multiple laps.
- Do not join a lap across an aborting transition such as `1→0`.
- Do not compare duplicate imports as independent driving attempts.
- Do not replace the boundary timestamps with capture filename or session creation time.
- Do not name a Nürburgring corner while the track mapping is `uncalibrated`; use distance or `micro-sector-N`.
- Do not promote wheel diagnostics beyond `suspected` without independent confirmation.
- Do not expose raw captures, SQLite contents, credentials, or private filesystem details in a public model prompt.

## Verification

Before giving a coaching answer, verify that:

- the command exited successfully and emitted valid JSON;
- the lap is complete and positive-numbered;
- duplicate sessions are excluded from independent-sample counts;
- the response quotes measured values from the payload;
- every recommendation is clearly labeled as model interpretation rather than analyzer fact.
