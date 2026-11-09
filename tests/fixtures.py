"""Synthetic bronze data with the same shape as the real sources (incl. their known quirks)."""
import datetime as dt
import json
import os

import pandas as pd


def _taxi_month(year, month, upper_airport_fee, with_cbd):
    base = dt.datetime(year, month, 3, 8, 0)
    rows = []
    for i in range(20):
        p = base + dt.timedelta(hours=i * 7)
        rows.append({"VendorID": 1 + i % 2, "tpep_pickup_datetime": p,
                     "tpep_dropoff_datetime": p + dt.timedelta(minutes=10 + i),
                     "passenger_count": float(1 + i % 3), "trip_distance": 1.5 + i,
                     "RatecodeID": 1.0, "store_and_fwd_flag": "N",
                     "PULocationID": 100 + i % 5, "DOLocationID": 140 + i % 7, "payment_type": 1,
                     "fare_amount": 10.0 + i, "extra": 0.5, "mta_tax": 0.5, "tip_amount": 2.0,
                     "tolls_amount": 0.0, "improvement_surcharge": 1.0, "total_amount": 15.0 + i,
                     "congestion_surcharge": 2.5, "fee": 0.0})
    bad = dict(rows[0])
    rows.append(dict(rows[1]))                                                  # exact duplicate
    rows.append({**bad, "tpep_pickup_datetime": dt.datetime(2002, 1, 1, 0, 0),
                 "tpep_dropoff_datetime": dt.datetime(2002, 1, 1, 0, 9)})        # outside file month
    rows.append({**bad, "tpep_dropoff_datetime": bad["tpep_pickup_datetime"]})  # zero duration
    rows.append({**bad, "total_amount": -5.0, "fare_amount": -5.0})            # negative amount
    rows.append({**bad, "PULocationID": 999})                                  # unknown zone
    df = pd.DataFrame(rows)
    df = df.rename(columns={"fee": "Airport_fee" if upper_airport_fee else "airport_fee"})
    if with_cbd:
        df["cbd_congestion_fee"] = 0.75
    df["PULocationID"] = df["PULocationID"].astype("int32")
    return df


def build_bronze(root, spark):
    files = f"{root}/bronze/Files"
    # taxi: 2024-12 (old schema: Airport_fee) and 2025-01 (new: airport_fee + cbd_congestion_fee)
    for (y, m, upper, cbd) in [(2024, 12, True, False), (2025, 1, False, True)]:
        d = f"{files}/raw/nyc_taxi/yellow/year={y}/month={m:02d}"
        os.makedirs(d, exist_ok=True)
        _taxi_month(y, m, upper, cbd).to_parquet(f"{d}/yellow_tripdata_{y}-{m:02d}.parquet", index=False)
    z = f"{files}/raw/nyc_taxi/zones"
    os.makedirs(z, exist_ok=True)
    with open(f"{z}/taxi_zone_lookup.csv", "w") as f:
        f.write('"LocationID","Borough","Zone","service_zone"\n')
        for i in range(1, 266):
            f.write(f'{i},"{["Manhattan","Brooklyn","Queens","Bronx","Staten Island"][i % 5]}","Zone {i}","Boro Zone"\n')
    # weather (Open-Meteo JSON)
    w = f"{files}/raw/weather/open_meteo/year=2025/month=01"
    os.makedirs(w, exist_ok=True)
    days = [f"2025-01-{d:02d}" for d in range(1, 32)]
    with open(f"{w}/weather_2025-01.json", "w") as f:
        json.dump({"latitude": 40.71, "daily": {"time": days, "temperature_2m_max": [3.0] * 31,
                   "temperature_2m_min": [-2.0] * 31, "temperature_2m_mean": [0.5] * 31,
                   "precipitation_sum": [1.2] * 31, "wind_speed_10m_max": [20.0] * 31}}, f)

    # dataflow tables (bronze Tables) - local tests use parquet instead of delta
    now = dt.datetime(2025, 2, 1, 6, 0)
    aq = []
    for d in range(1, 11):
        day = dt.date(2025, 1, d)
        aq.append((101, 11, "Manhattan PS 19", 40.73, -73.98, "pm25", "µg/m³", day, 9.0 + d, 4.0, 20.0, 95.0, now))
        aq.append((202, 22, "Queens College", 40.737, -73.82, "no2", "ppm", day, 0.02, 0.01, 0.03, 90.0, now))
        aq.append((303, 33, "Jersey City", 40.72, -74.05, "pm25", "µg/m³", day, 8.0, 3.0, 12.0, 80.0, now))
    aq.append((101, 11, "Manhattan PS 19", 40.73, -73.98, "pm25", "µg/m³", dt.date(2025, 1, 1), 99.0, 4.0, 20.0, 95.0,
               dt.datetime(2025, 1, 15)))                                    # older duplicate -> dropped
    aq.append((404, 44, "Bronx", 40.84, -73.86, "pm25", "µg/m³", dt.date(2025, 1, 2), -3.0, -3.0, 0.0, 50.0, now))  # negative
    spark.createDataFrame(aq, "sensor_id long, location_id long, location_name string, latitude double, longitude double, "
                              "parameter string, units string, date date, value double, min double, max double, "
                              "coverage_pct double, ingested_at timestamp"
                          ).write.mode("overwrite").parquet(f"{root}/bronze/Tables/openaq_sensor_days")
    gdp = [("USA", "United States", str(y), 2.0e13 + y * 1e11, now) for y in range(2018, 2025)]
    gdp.append(("USA", "United States", "2025", None, now))
    spark.createDataFrame(gdp, "country_code string, country_name string, year string, value double, ingested_at timestamp"
                          ).write.mode("overwrite").parquet(f"{root}/bronze/Tables/worldbank_gdp")
    fx = [("2025-01-02", 1.0321), ("2025-01-03", 1.0299), ("2025-01-06", 1.0426), ("2025-01-07", 1.0393)]
    spark.createDataFrame([(d, v, "USD", "EUR", now) for d, v in fx],
                          "time_period string, obs_value double, currency string, currency_denom string, ingested_at timestamp"
                          ).write.mode("overwrite").parquet(f"{root}/bronze/Tables/ecb_fx")
