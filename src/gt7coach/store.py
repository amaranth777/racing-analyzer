"""SQLite persistence for decoded GT7 capture frames."""
from __future__ import annotations
import sqlite3, struct
from pathlib import Path
from .analysis import cumulative_distance, summarize_segments
from .comparison import compare_laps
from .diagnostics import control_metrics, detect_events, detect_wheel_events, wheel_speeds_kmh
from .laps import extract_lap_boundaries
from .protocol import PacketError, TelemetryPacket, decode_packet
from .state import classify_packet_state, coalesce_states

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
 id INTEGER PRIMARY KEY, source_path TEXT NOT NULL, started_ns INTEGER NOT NULL,
 ended_ns INTEGER NOT NULL, packet_count INTEGER NOT NULL, packet_size INTEGER NOT NULL,
 car_code INTEGER NOT NULL, decode_errors INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS frames (
 session_id INTEGER NOT NULL REFERENCES sessions(id), seq INTEGER NOT NULL,
 ts_ns INTEGER NOT NULL, packet_id INTEGER NOT NULL, lap INTEGER NOT NULL,
 best_lap_ms INTEGER NOT NULL, last_lap_ms INTEGER NOT NULL, flags INTEGER NOT NULL,
 x REAL NOT NULL, y REAL NOT NULL, z REAL NOT NULL, speed_mps REAL NOT NULL,
 rpm REAL NOT NULL, throttle REAL NOT NULL, brake REAL NOT NULL, gear INTEGER NOT NULL,
 suggested_gear INTEGER NOT NULL, wheel_rotation REAL NOT NULL, sway REAL NOT NULL,
 heave REAL NOT NULL, surge REAL NOT NULL, PRIMARY KEY(session_id, seq));
CREATE INDEX IF NOT EXISTS frames_lap_idx ON frames(session_id, lap, seq);
CREATE TABLE IF NOT EXISTS setups (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 track_id TEXT NOT NULL,
 car_code INTEGER NOT NULL,
 name TEXT NOT NULL,
 notes TEXT NOT NULL DEFAULT '',
 created_ns INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS setups_filter_idx ON setups(track_id, car_code, created_ns);
CREATE TABLE IF NOT EXISTS wheel_frames (
 session_id INTEGER NOT NULL REFERENCES sessions(id),
 seq INTEGER NOT NULL,
 front_left_rps REAL NOT NULL, front_right_rps REAL NOT NULL,
 rear_left_rps REAL NOT NULL, rear_right_rps REAL NOT NULL,
 front_left_diameter_m REAL NOT NULL, front_right_diameter_m REAL NOT NULL,
 rear_left_diameter_m REAL NOT NULL, rear_right_diameter_m REAL NOT NULL,
 PRIMARY KEY(session_id, seq)
);
CREATE TABLE IF NOT EXISTS state_spans (
 session_id INTEGER NOT NULL REFERENCES sessions(id),
 start_seq INTEGER NOT NULL,
 end_seq INTEGER NOT NULL,
 kind TEXT NOT NULL,
 start_ts_ns INTEGER NOT NULL,
 end_ts_ns INTEGER NOT NULL,
 PRIMARY KEY(session_id, start_seq)
);
CREATE INDEX IF NOT EXISTS state_spans_kind_idx
 ON state_spans(session_id, kind, start_seq);
"""

def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn

def _raw_frames(path: Path):
    with path.open('rb') as stream:
        while True:
            header = stream.read(12)
            if not header:
                return
            if len(header) != 12:
                raise ValueError('truncated raw frame header')
            ts_ns, size = struct.unpack('<QI', header)
            payload = stream.read(size)
            if len(payload) != size:
                raise ValueError('truncated raw frame payload')
            yield ts_ns, payload

def _frame_values(session_id: int, seq: int, ts_ns: int, p: TelemetryPacket):
    x, y, z = p.position
    return (session_id, seq, ts_ns, p.packet_id, p.lap, p.best_lap_ms,
            p.last_lap_ms, p.flags, x, y, z, p.speed_mps, p.rpm, p.throttle,
            p.brake, p.gear, p.suggested_gear, p.wheel_rotation_rad, p.sway,
            p.heave, p.surge)

def import_capture(db: str | Path, source: str | Path) -> int:
    source = Path(source)
    conn = connect(db)
    started = ended = None
    count = errors = packet_size = car_code = 0
    states = []
    cur = conn.cursor()
    with conn:
        cur.execute('INSERT INTO sessions(source_path,started_ns,ended_ns,packet_count,packet_size,car_code) VALUES(?,?,?,?,?,?)', (str(source), 0, 0, 0, 0, 0))
        session_id = int(cur.lastrowid)
        for seq, (ts_ns, payload) in enumerate(_raw_frames(source)):
            started = ts_ns if started is None else started
            ended = ts_ns
            packet_size = len(payload)
            try:
                packet = decode_packet(payload)
            except PacketError:
                errors += 1
                continue
            car_code = packet.car_code
            cur.execute('INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', _frame_values(session_id, seq, ts_ns, packet))
            cur.execute(
                'INSERT INTO wheel_frames VALUES(?,?,?,?,?,?,?,?,?,?)',
                (session_id, seq, *packet.wheel_rps, *packet.tyre_diameter_m),
            )
            states.append((seq, ts_ns, classify_packet_state(packet)))
            count += 1
        cur.executemany(
            'INSERT INTO state_spans(session_id,start_seq,end_seq,kind,start_ts_ns,end_ts_ns) VALUES(?,?,?,?,?,?)',
            (
                (session_id, span["start_seq"], span["end_seq"], span["kind"],
                 span["start_ts_ns"], span["end_ts_ns"])
                for span in coalesce_states(states)
            ),
        )
        cur.execute('UPDATE sessions SET started_ns=?,ended_ns=?,packet_count=?,packet_size=?,car_code=?,decode_errors=? WHERE id=?', (started or 0, ended or 0, count, packet_size, car_code, errors, session_id))
    conn.close()
    return session_id

def session_summary(db: str | Path, session_id: int | None = None) -> dict:
    conn = connect(db)
    row = conn.execute('SELECT * FROM sessions WHERE id=COALESCE(?,(SELECT max(id) FROM sessions))', (session_id,)).fetchone()
    if row is None:
        raise ValueError('no imported sessions')
    frames = conn.execute('SELECT * FROM frames WHERE session_id=? ORDER BY seq', (row['id'],)).fetchall()
    transitions = []
    for a, b in zip(frames, frames[1:]):
        if a['lap'] != b['lap']:
            transitions.append({'seq': b['seq'], 'from': a['lap'], 'to': b['lap'], 'last_lap_ms': a['last_lap_ms']})
    lap_boundaries = extract_lap_boundaries(frames)
    max_speed = max((x['speed_mps'] for x in frames), default=0.0) * 3.6
    result = {
        'session_id': row['id'], 'source_path': row['source_path'],
        'frames': len(frames), 'decode_errors': row['decode_errors'],
        'packet_size': row['packet_size'], 'car_code': row['car_code'],
        'duration_s': round((row['ended_ns'] - row['started_ns']) / 1e9, 3),
        'laps_seen': sorted({x['lap'] for x in frames}),
        'lap_transitions': transitions,
        'completed_laps': [
            {'lap': boundary.lap, 'lap_time_s': round(boundary.lap_time_ms / 1000, 3),
             'start_seq': boundary.start_seq, 'end_seq': boundary.end_seq,
             'start_ts_ns': boundary.start_ts_ns, 'end_ts_ns': boundary.end_ts_ns}
            for boundary in lap_boundaries
        ],
        'max_speed_kmh': round(max_speed, 1),
    }
    conn.close()
    return result


def session_analysis(db, session_id=None, segment_m=200.0):
    """Analyze the last complete positive-numbered lap in a session."""
    conn = connect(db)
    row = conn.execute(
        'SELECT * FROM sessions WHERE id=COALESCE(?,(SELECT max(id) FROM sessions))',
        (session_id,),
    ).fetchone()
    if row is None:
        raise ValueError('no imported sessions')
    frames = conn.execute(
        'SELECT * FROM frames WHERE session_id=? ORDER BY seq', (row['id'],)
    ).fetchall()
    boundaries = extract_lap_boundaries(frames)
    if not boundaries:
        raise ValueError('no complete positive lap found')
    boundary = boundaries[-1]
    lap_number = boundary.lap
    lap_rows = [
        frame for frame in frames
        if boundary.start_seq <= frame['seq'] < boundary.end_seq
    ]
    rows = [
        {'x': f['x'], 'y': f['y'], 'z': f['z'], 'speed_mps': f['speed_mps'],
         'throttle': f['throttle'], 'brake': f['brake'],
         'wheel_rotation': f['wheel_rotation'], 'ts_ns': f['ts_ns']}
        for f in lap_rows
    ]
    distances = cumulative_distance(rows)
    for row_data, distance in zip(rows, distances):
        row_data['distance_m'] = distance
    segments = summarize_segments(rows, segment_m=segment_m)
    events = detect_events(rows)
    controls = control_metrics(rows)
    wheel_by_seq = {
        item["seq"]: item for item in conn.execute(
            "SELECT * FROM wheel_frames WHERE session_id=?", (row["id"],)
        ).fetchall()
    }
    wheel_rows = []
    for frame, row_data in zip(lap_rows, rows):
        wheel = wheel_by_seq.get(frame["seq"])
        if wheel is None:
            continue
        rps = (wheel["front_left_rps"], wheel["front_right_rps"],
               wheel["rear_left_rps"], wheel["rear_right_rps"])
        diameters = (wheel["front_left_diameter_m"], wheel["front_right_diameter_m"],
                     wheel["rear_left_diameter_m"], wheel["rear_right_diameter_m"])
        row_data["wheel_speeds_kmh"] = wheel_speeds_kmh(rps, diameters)
        wheel_rows.append(row_data)
    wheel_events = detect_wheel_events(wheel_rows) if wheel_rows else []
    distance_m = sum(
        ((float(b['x']) - float(a['x'])) ** 2 +
         (float(b['y']) - float(a['y'])) ** 2 +
         (float(b['z']) - float(a['z'])) ** 2) ** 0.5
        for a, b in zip(lap_rows, lap_rows[1:])
    )
    conn.close()
    return {
        'session_id': row['id'], 'lap': lap_number, 'frames': len(lap_rows),
        'lap_time_s': round(boundary.lap_time_ms / 1000, 3),
        'start_seq': boundary.start_seq, 'end_seq': boundary.end_seq,
        'start_ts_ns': boundary.start_ts_ns, 'end_ts_ns': boundary.end_ts_ns,
        'distance_m': round(distance_m, 1), 'segment_m': segment_m,
        'segment_count': len(segments),
        'events': events,
        'control_metrics': controls,
        'wheel_events': wheel_events,
        'slowest_segments': sorted(segments, key=lambda x: x['mean_speed_kmh'])[:10],
        'segments': segments,
    }


def session_comparison(db, session_id=None, segment_m=200.0):
    """Compare all complete positive-numbered laps in a session."""
    conn = connect(db)
    row = conn.execute(
        'SELECT * FROM sessions WHERE id=COALESCE(?,(SELECT max(id) FROM sessions))',
        (session_id,),
    ).fetchone()
    if row is None:
        raise ValueError('no imported sessions')
    frames = conn.execute(
        'SELECT * FROM frames WHERE session_id=? ORDER BY seq', (row['id'],)
    ).fetchall()
    boundaries = extract_lap_boundaries(frames)
    if len(boundaries) < 2:
        raise ValueError('at least two complete positive laps are required')
    lap_rows = {
        boundary.lap: [
            {'x': frame['x'], 'y': frame['y'], 'z': frame['z'],
             'ts_ns': frame['ts_ns'], 'speed_mps': frame['speed_mps'],
             'throttle': frame['throttle'], 'brake': frame['brake'],
             'wheel_rotation': frame['wheel_rotation']}
            for frame in frames
            if boundary.start_seq <= frame['seq'] < boundary.end_seq
        ]
        for boundary in boundaries
    }
    conn.close()
    result = compare_laps(lap_rows, segment_m=segment_m)
    metadata = {
        boundary.lap: {
            'lap': boundary.lap,
            'lap_time_s': round(boundary.lap_time_ms / 1000, 3),
            'start_seq': boundary.start_seq,
            'end_seq': boundary.end_seq,
            'start_ts_ns': boundary.start_ts_ns,
            'end_ts_ns': boundary.end_ts_ns,
        }
        for boundary in boundaries
    }
    result['laps'] = [metadata[item['lap']] for item in result['laps']]
    return result


def compare_sessions(db, session_ids, segment_m=200.0):
    """Compare the last complete lap from each explicitly selected session."""
    if len(session_ids) < 2:
        raise ValueError('at least two session IDs are required')
    conn = connect(db)
    lap_rows = {}
    metadata = {}
    for session_id in session_ids:
        row = conn.execute('SELECT * FROM sessions WHERE id=?', (int(session_id),)).fetchone()
        if row is None:
            raise ValueError(f'session {session_id} not found')
        frames = conn.execute(
            'SELECT * FROM frames WHERE session_id=? ORDER BY seq', (row['id'],)
        ).fetchall()
        boundaries = extract_lap_boundaries(frames)
        if not boundaries:
            raise ValueError(f'session {session_id} has no complete positive lap')
        boundary = boundaries[-1]
        lap_rows[int(session_id)] = [
            {'x': frame['x'], 'y': frame['y'], 'z': frame['z'],
             'ts_ns': frame['ts_ns'], 'speed_mps': frame['speed_mps'],
             'throttle': frame['throttle'], 'brake': frame['brake'],
             'wheel_rotation': frame['wheel_rotation']}
            for frame in frames
            if boundary.start_seq <= frame['seq'] < boundary.end_seq
        ]
        metadata[int(session_id)] = {
            'session_id': int(session_id),
            'lap': boundary.lap,
            'lap_time_s': round(boundary.lap_time_ms / 1000, 3),
            'start_seq': boundary.start_seq,
            'end_seq': boundary.end_seq,
            'start_ts_ns': boundary.start_ts_ns,
            'end_ts_ns': boundary.end_ts_ns,
        }
    conn.close()
    result = compare_laps(lap_rows, segment_m=segment_m)
    result['best_session_id'] = min(
        metadata, key=lambda session_id: metadata[session_id]['lap_time_s']
    )
    result['slowest_session_id'] = max(
        metadata, key=lambda session_id: metadata[session_id]['lap_time_s']
    )
    best_time = metadata[result['best_session_id']]['lap_time_s']
    slowest_time = metadata[result['slowest_session_id']]['lap_time_s']
    result['delta_s'] = round(slowest_time - best_time, 3)
    result['delta_pct'] = round(result['delta_s'] / best_time * 100, 2)
    result['laps'] = [metadata[int(item['lap'])] for item in result['laps']]
    result['segment_winners'] = [
        {**winner, 'session_id': winner.pop('lap')}
        for winner in result['segment_winners']
    ]
    result.pop('best_lap', None)
    return result


def add_setup(db, *, track_id, car_code, name, notes=''):
    """Record one manually named setup version."""
    import time
    if not str(track_id).strip() or not str(name).strip():
        raise ValueError('track_id and name are required')
    conn = connect(db)
    created_ns = time.time_ns()
    with conn:
        cursor = conn.execute(
            'INSERT INTO setups(track_id,car_code,name,notes,created_ns) VALUES(?,?,?,?,?)',
            (str(track_id), int(car_code), str(name), str(notes), created_ns),
        )
        setup_id = cursor.lastrowid
    row = conn.execute('SELECT * FROM setups WHERE id=?', (setup_id,)).fetchone()
    conn.close()
    return dict(row)


def list_setups(db, *, track_id=None, car_code=None):
    """List setup versions, newest first, with optional exact filters."""
    conn = connect(db)
    clauses = []
    values = []
    if track_id is not None:
        clauses.append('track_id=?')
        values.append(str(track_id))
    if car_code is not None:
        clauses.append('car_code=?')
        values.append(int(car_code))
    where = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
    rows = conn.execute(
        'SELECT * FROM setups' + where + ' ORDER BY created_ns DESC, id DESC', values
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]
