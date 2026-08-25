import json
import sqlite3

from gt7coach.store import SCHEMA, add_setup, list_setups


def test_setup_log_round_trip_and_filters(tmp_path):
    db = tmp_path / "setups.sqlite3"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    conn.commit(); conn.close()

    first = add_setup(db, track_id="nurburgring_nordschleife", car_code=1365,
                      name="R8 baseline", notes="comfort-safe baseline")
    add_setup(db, track_id="suzuka", car_code=42,
              name="other", notes="not this car")

    assert first["name"] == "R8 baseline"
    assert first["notes"] == "comfort-safe baseline"
    assert len(list_setups(db, track_id="nurburgring_nordschleife", car_code=1365)) == 1
    assert list_setups(db, track_id="suzuka")[0]["car_code"] == 42
