"""End-to-end test of the Silver layer on synthetic bronze data (local Spark, parquet instead of Delta)."""
import copy
import datetime as dt

import pytest

from conftest import run_notebook
from fixtures import build_bronze


@pytest.fixture(scope="module")
def lake_env(spark, config, tmp_path_factory, monkeypatch_module):
    root = str(tmp_path_factory.mktemp("lake"))
    monkeypatch_module.setenv("LOCAL_LAKE_ROOT", root)
    build_bronze(root, spark)
    cfg = copy.deepcopy(config)
    for s in cfg["sources"]:
        if s["name"] == "weather_nyc_daily":
            s["enabled"] = True                      # the extension source is part of the test
    return root, cfg


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def run_silver(spark, cfg, sources="all"):
    ns = {"spark": spark, "sources": sources, "run_id": "test"}
    run_notebook("nb_common", ns)
    ns["load_config"] = lambda *a, **kw: cfg
    run_notebook("nb_transforms", ns)
    exec(compile(_driver_code(), "nb_silver_load.py", "exec"), ns)
    return ns


def _driver_code():
    from conftest import notebook_code
    code = notebook_code("nb_silver_load")
    # parameters are injected through the namespace (like Fabric's parameter cell)
    return code.replace('sources = "all"', '').replace('run_id = ""', '')


def table(spark, ns, name):
    lake = ns["lake"]
    return spark.read.parquet(lake.silver_table(name))


def test_full_silver_run(spark, lake_env):
    root, cfg = lake_env
    ns = run_silver(spark, cfg)

    trips = table(spark, ns, "taxi_trips")
    assert trips.count() == 40                                   # 2 x 25 rows - 4 rejected - 1 duplicate
    assert {"airport_fee", "cbd_congestion_fee", "trip_id", "year_month", "duration_min"} <= set(trips.columns)
    by_month = {r.year_month: r["count"] for r in trips.groupBy("year_month").count().collect()}
    assert by_month == {"2024-12": 20, "2025-01": 20}
    assert trips.where("year_month = '2025-01' AND cbd_congestion_fee = 0.75").count() == 20
    assert trips.where("year_month = '2024-12' AND cbd_congestion_fee IS NULL").count() == 20
    assert trips.select("trip_id").distinct().count() == 40

    log = table(spark, ns, "_load_log")
    taxi_log = log.where("source = 'nyc_taxi_yellow'").collect()
    assert len(taxi_log) == 2
    assert all(r.rows_in == 25 and r.rows_rejected == 4 and r.rows_out == 20 for r in taxi_log)

    zones = table(spark, ns, "taxi_zones")
    assert zones.count() == 265

    aq = table(spark, ns, "air_quality_daily")
    assert aq.count() == 30
    no2 = aq.where("parameter = 'no2'").select("value_avg", "units").distinct().collect()
    assert [(r.value_avg, r.units) for r in no2] == [(20.0, "ppb")]          # 0.02 ppm -> 20 ppb
    boroughs = {r.location_name: r.borough for r in aq.select("location_name", "borough").distinct().collect()}
    assert boroughs == {"Manhattan PS 19": "Manhattan", "Queens College": "Queens", "Jersey City": "New Jersey"}
    assert aq.where("sensor_id = 101 AND date = DATE'2025-01-01'").collect()[0].value_avg == 10.0   # newest wins

    gdp = table(spark, ns, "gdp_yearly")
    assert gdp.count() == 7

    fx = table(spark, ns, "fx_daily")
    sat = fx.where("date = DATE'2025-01-04'").collect()[0]
    assert sat.usd_per_eur == 1.0299 and sat.is_published is False      # weekend: last published rate
    assert fx.where("date = DATE'2025-01-06'").collect()[0].is_published is True
    assert fx.agg({"date": "max"}).collect()[0][0] == dt.date.today()

    weather = table(spark, ns, "weather_daily")
    assert weather.count() == 31

    cal = table(spark, ns, "calendar")
    jan6 = cal.where("date = DATE'2025-01-06'").collect()[0]
    assert jan6.date_key == 20250106 and jan6.day_of_week == 1 and jan6.day_name == "Monday" and not jan6.is_weekend


def test_rerun_is_idempotent(spark, lake_env):
    root, cfg = lake_env
    ns = run_silver(spark, cfg)                                   # second run: no new files
    assert table(spark, ns, "taxi_trips").count() == 40
    taxi_log = table(spark, ns, "_load_log").where("source = 'nyc_taxi_yellow'").count()
    assert taxi_log == 2                                          # nothing re-processed
    assert table(spark, ns, "air_quality_daily").count() == 30   # merge, no duplicates


def test_reprocess_changed_month(spark, lake_env):
    """A re-downloaded month replaces only its own partition."""
    import os
    import time
    from fixtures import _taxi_month
    root, cfg = lake_env
    p = f"{root}/bronze/Files/raw/nyc_taxi/yellow/year=2025/month=01/yellow_tripdata_2025-01.parquet"
    time.sleep(1.1)
    _taxi_month(2025, 1, False, True).head(10).to_parquet(p, index=False)   # smaller corrected file
    os.utime(p, None)
    ns = run_silver(spark, cfg, sources="nyc_taxi_yellow")
    by_month = {r.year_month: r["count"] for r in table(spark, ns, "taxi_trips").groupBy("year_month").count().collect()}
    assert by_month == {"2024-12": 20, "2025-01": 10}


def test_transform_helpers(spark):
    ns = {"spark": spark}
    run_notebook("nb_common", ns)
    run_notebook("nb_transforms", ns)
    assert ns["snake"]("PULocationID") == "pulocationid"
    assert ns["snake"]("Airport_fee") == "airport_fee"
    assert ns["render"]("trip-data/yellow_{yyyy}-{mm}.parquet", yyyy="2025", mm="03") == "trip-data/yellow_2025-03.parquet"
    assert ns["landing_root"]("raw/nyc_taxi/yellow/year={yyyy}/month={mm}") == "raw/nyc_taxi/yellow"
    assert ns["month_range"](dt.date(2024, 11, 15), dt.date(2025, 2, 1)) == [(2024, 11), (2024, 12), (2025, 1), (2025, 2)]
    assert ns["month_values"](2024, 2)["month_end"] == "2024-02-29"
