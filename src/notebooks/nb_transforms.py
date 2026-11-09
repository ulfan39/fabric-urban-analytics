# %% [markdown]
# # nb_transforms
# Bronze -> Silver transformations, one function per `silver.transform` name in `config/sources.json`.
#
# Signature of every transform: `fn(spark, lake, src, files) -> (DataFrame, stats)`
# * `files` - new bronze files for file based sources, `None` for sources loaded by a dataflow
# * `stats` - `{bronze_file or "*": {"rows_in": n, "rows_rejected": n}}`, written to `_load_log`
#
# Rows that break a data-quality rule get a `dq_reason` and are counted as rejected.
# Duplicates are removed silently (they show up as rows_in - rows_rejected - rows_out).

# %%
import re

from pyspark.sql import functions as F
from pyspark.sql.window import Window


def snake(name):
    """'PULocationID' -> 'pulocationid', 'Airport_fee' -> 'airport_fee'"""
    return re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()


def snake_columns(df):
    return df.toDF(*[snake(c) for c in df.columns])


def conform(df, schema):
    """Target columns in a fixed order and type; a column missing in this file becomes NULL."""
    return df.select(*[(F.col(c) if c in df.columns else F.lit(None)).cast(t).alias(c) for c, t in schema])


def reject_stats(df):
    """Counts per source_file of a frame with a dq_reason column (NULL = valid row)."""
    rows = (df.groupBy("source_file")
              .agg(F.count("*").alias("rows_in"), F.count("dq_reason").alias("rows_rejected"))
              .collect())
    return {r.source_file: {"rows_in": r.rows_in, "rows_rejected": r.rows_rejected} for r in rows}


def latest_per_key(df, keys):
    """Keeps the most recently ingested row per key (dataflows replace the whole bronze table)."""
    w = Window.partitionBy(*keys).orderBy(F.col("ingested_at").desc())
    return df.withColumn("_rn", F.row_number().over(w)).where("_rn = 1").drop("_rn")


def read_bronze_table(spark, lake, src):
    df = snake_columns(read_table(spark, lake, lake.bronze_table(src["bronze"]["bronze_table"])))
    return df.withColumn("source_file", F.lit("*"))


# ------------------------------------------------------------------ NYC taxi trips
TAXI_SCHEMA = [
    ("vendorid", "int"), ("pickup_ts", "timestamp"), ("dropoff_ts", "timestamp"),
    ("passenger_count", "int"), ("trip_distance", "double"), ("ratecodeid", "int"),
    ("store_and_fwd_flag", "string"), ("pulocationid", "int"), ("dolocationid", "int"),
    ("payment_type", "int"), ("fare_amount", "double"), ("extra", "double"), ("mta_tax", "double"),
    ("tip_amount", "double"), ("tolls_amount", "double"), ("improvement_surcharge", "double"),
    ("total_amount", "double"), ("congestion_surcharge", "double"), ("airport_fee", "double"),
    ("cbd_congestion_fee", "double"),
]
TAXI_RENAMES = {"vendorid": "vendor_id", "ratecodeid": "rate_code_id",
                "pulocationid": "pu_location_id", "dolocationid": "do_location_id"}
TAXI_KEY = ["service", "vendor_id", "pickup_ts", "dropoff_ts", "pu_location_id", "do_location_id",
            "trip_distance", "total_amount"]


def taxi_trips(spark, lake, src, files):
    # The monthly files do not share one schema (Airport_fee / airport_fee, int / double,
    # cbd_congestion_fee since 2025), so each file is read and conformed separately.
    opts = src["silver"]["options"]
    df = None
    for path, _, _ in files:
        month = re.search(r"(\d{4}-\d{2})\.parquet$", path).group(1)
        part = (snake_columns(spark.read.parquet(path))
                .withColumnRenamed(snake(opts["pickup_col"]), "pickup_ts")
                .withColumnRenamed(snake(opts["dropoff_col"]), "dropoff_ts"))
        part = conform(part, TAXI_SCHEMA).withColumn("source_file", F.lit(path)).withColumn("year_month", F.lit(month))
        df = part if df is None else df.unionByName(part)
    for old, new in TAXI_RENAMES.items():
        df = df.withColumnRenamed(old, new)

    df = (df.withColumn("service", F.lit(opts["service"]))
            .withColumn("duration_min", F.round((F.unix_timestamp("dropoff_ts") - F.unix_timestamp("pickup_ts")) / 60, 2))
            .withColumn("pickup_date", F.to_date("pickup_ts"))
            .withColumn("pickup_hour", F.hour("pickup_ts")))
    reason = (F.when(F.col("pickup_ts").isNull() | F.col("dropoff_ts").isNull(), "missing_timestamp")
               .when(F.date_format("pickup_ts", "yyyy-MM") != F.col("year_month"), "pickup_outside_file_month")
               .when((F.col("duration_min") <= 0) | (F.col("duration_min") > 360), "bad_duration")
               .when((F.col("trip_distance") < 0) | (F.col("trip_distance") > 200), "bad_distance")
               .when((F.col("fare_amount") < 0) | (F.col("total_amount") < 0), "negative_amount")
               .when(~F.col("pu_location_id").between(1, 265) | ~F.col("do_location_id").between(1, 265), "bad_zone"))
    df = df.withColumn("dq_reason", reason).cache()

    out = (df.where("dq_reason IS NULL").drop("dq_reason")
             .dropDuplicates(TAXI_KEY)
             .withColumn("trip_id", F.sha2(F.concat_ws("|", *[F.col(c).cast("string") for c in TAXI_KEY]), 256))
             .withColumn("ingested_at", F.current_timestamp()))
    return out, reject_stats(df)


# ------------------------------------------------------------------ taxi zones
def taxi_zones(spark, lake, src, files):
    path = files[0][0]                     # a single lookup file, re-copied when it changes
    df = (snake_columns(spark.read.option("header", True).csv(path))
          .select(F.col("locationid").cast("int").alias("location_id"), F.trim("borough").alias("borough"),
                  F.trim("zone").alias("zone"), F.trim("service_zone").alias("service_zone"))
          .withColumn("source_file", F.lit(path))
          .withColumn("dq_reason", F.when(F.col("location_id").isNull(), "missing_location_id"))
          .cache())
    out = (df.where("dq_reason IS NULL").drop("dq_reason", "source_file")
             .dropDuplicates(["location_id"]).withColumn("ingested_at", F.current_timestamp()))
    return out, reject_stats(df)


# ------------------------------------------------------------------ OpenAQ air quality
# Borough of a monitoring site, approximated: nearest borough centre within 12 km,
# sites west of the Hudson are New Jersey. A join with the TLC zone polygons would be exact.
BOROUGH_CENTRES = [("Manhattan", 40.7831, -73.9712), ("Brooklyn", 40.6782, -73.9442),
                   ("Queens", 40.7282, -73.7949), ("Bronx", 40.8448, -73.8648),
                   ("Staten Island", 40.5795, -74.1502)]
KM_PER_DEG_LAT, KM_PER_DEG_LON = 111.0, 84.3          # at latitude 40.7


def borough_of(lat, lon):
    dist = {name: F.sqrt(((lat - la) * KM_PER_DEG_LAT) ** 2 + ((lon - lo) * KM_PER_DEG_LON) ** 2)
            for name, la, lo in BOROUGH_CENTRES}
    nearest = F.least(*dist.values())
    expr = F.when(lat.isNull() | lon.isNull(), "Unknown").when((lon < -74.03) & (lat > 40.64), "New Jersey")
    expr = expr.when(nearest > 12, "Outside NYC")
    for name, d in dist.items():
        expr = expr.when(d == nearest, name)
    return expr


def air_quality_daily(spark, lake, src, files):
    # Standard units: PM2.5 in ug/m3, NO2 in ppb (sensors report ppm or ug/m3; 1 ppb NO2 = 1.88 ug/m3).
    df = latest_per_key(read_bronze_table(spark, lake, src), ["sensor_id", "date"])
    df = (df.withColumn("parameter", F.lower(F.trim("parameter")))
            .withColumn("units_source", F.trim("units")))
    no2 = F.col("parameter") == "no2"
    factor = (F.when(no2 & (F.lower("units_source") == "ppm"), 1000.0)
               .when(no2 & F.lower("units_source").isin("µg/m³", "ug/m3"), 1 / 1.88)
               .otherwise(1.0))
    df = (df.withColumn("units", F.when(no2, "ppb").otherwise("ug/m3"))
            .withColumn("value_avg", F.round(F.col("value") * factor, 3))
            .withColumn("value_min", F.round(F.col("min") * factor, 3))
            .withColumn("value_max", F.round(F.col("max") * factor, 3))
            .withColumn("borough", borough_of(F.col("latitude"), F.col("longitude")))
            .withColumn("dq_reason",
                        F.when(F.col("value_avg").isNull(), "missing_value")
                         .when(F.col("value_avg") < 0, "negative_value")
                         .when(~F.col("parameter").isin(*src["bronze"]["params"]["parameters"]), "unexpected_parameter"))
            .cache())
    out = (df.where("dq_reason IS NULL")
             .select("sensor_id", "location_id", "location_name", "latitude", "longitude", "borough", "parameter",
                     "units_source", "units", F.to_date("date").alias("date"), "value_avg", "value_min", "value_max",
                     F.col("coverage_pct").cast("double").alias("coverage_pct"))
             .withColumn("ingested_at", F.current_timestamp()))
    return out, reject_stats(df)


# ------------------------------------------------------------------ World Bank GDP
def gdp_yearly(spark, lake, src, files):
    df = (latest_per_key(read_bronze_table(spark, lake, src), ["country_code", "year"])
          .withColumn("dq_reason", F.when(F.col("value").isNull(), "no_value_published").when(F.col("year").cast("int").isNull(), "bad_year"))
          .cache())
    out = (df.where("dq_reason IS NULL")
             .select(F.upper(F.trim("country_code")).alias("country_code"), F.trim("country_name").alias("country_name"),
                     F.col("year").cast("int").alias("year"), F.col("value").cast("double").alias("gdp_usd"))
             .withColumn("ingested_at", F.current_timestamp()))
    return out, reject_stats(df)


# ------------------------------------------------------------------ ECB FX
def fx_daily(spark, lake, src, files):
    # The ECB publishes on working days only; silver has every calendar day and
    # carries the last published rate forward (is_published = false on those days).
    df = (read_bronze_table(spark, lake, src)
          .withColumn("date", F.to_date("time_period"))
          .withColumn("usd_per_eur", F.col("obs_value").cast("double"))
          .withColumn("dq_reason", F.when(F.col("date").isNull(), "bad_date").when(F.col("usd_per_eur").isNull() | (F.col("usd_per_eur") <= 0), "bad_rate"))
          .cache())
    published = df.where("dq_reason IS NULL").select("date", "usd_per_eur").dropDuplicates(["date"])
    first_day = published.agg(F.min("date")).first()[0]
    days = spark.sql(f"SELECT explode(sequence(DATE'{first_day}', current_date(), INTERVAL 1 DAY)) AS date")
    carry = Window.orderBy("date").rowsBetween(Window.unboundedPreceding, 0)
    out = (days.join(published, "date", "left")
               .withColumn("is_published", F.col("usd_per_eur").isNotNull())
               .withColumn("usd_per_eur", F.last("usd_per_eur", ignorenulls=True).over(carry))
               .withColumn("eur_per_usd", F.round(1 / F.col("usd_per_eur"), 6))
               .withColumn("ingested_at", F.current_timestamp()))
    return out, reject_stats(df)


# ------------------------------------------------------------------ Open-Meteo weather (added as an extension)
WEATHER_FIELDS = ["temperature_2m_max", "temperature_2m_min", "temperature_2m_mean",
                  "precipitation_sum", "wind_speed_10m_max"]


def weather_daily(spark, lake, src, files):
    # Open-Meteo returns {"daily": {"time": [...], "<field>": [...], ...}}: parallel arrays -> one row per day.
    raw = (spark.read.option("multiLine", True).json([p for p, _, _ in files])
           .withColumn("source_file", F.input_file_name()))
    days = raw.select("source_file", F.explode(F.arrays_zip("daily.time", *[f"daily.{f}" for f in WEATHER_FIELDS])).alias("d"))
    df = (days.select("source_file", F.to_date("d.time").alias("date"),
                      *[F.col(f"d.{f}").cast("double").alias(f) for f in WEATHER_FIELDS])
              .withColumn("dq_reason", F.when(F.col("date").isNull(), "missing_date"))
              .cache())
    out = (df.where("dq_reason IS NULL").drop("dq_reason", "source_file")
             .dropDuplicates(["date"]).withColumn("ingested_at", F.current_timestamp()))
    return out, reject_stats(df)


TRANSFORMS = {
    "taxi_trips": taxi_trips,
    "taxi_zones": taxi_zones,
    "air_quality_daily": air_quality_daily,
    "gdp_yearly": gdp_yearly,
    "fx_daily": fx_daily,
    "weather_daily": weather_daily,
}


# ------------------------------------------------------------------ calendar (source of DimDate)
def build_calendar(spark, start, end):
    df = spark.sql(f"SELECT explode(sequence(DATE'{start}', DATE'{end}', INTERVAL 1 DAY)) AS date")
    return (df.withColumn("date_key", F.date_format("date", "yyyyMMdd").cast("int"))
              .withColumn("year", F.year("date"))
              .withColumn("quarter", F.quarter("date"))
              .withColumn("month", F.month("date"))
              .withColumn("month_name", F.date_format("date", "MMMM"))
              .withColumn("year_month", F.date_format("date", "yyyy-MM"))
              .withColumn("day", F.dayofmonth("date"))
              .withColumn("day_of_week", F.weekday("date") + 1)          # 1 = Monday ... 7 = Sunday
              .withColumn("day_name", F.date_format("date", "EEEE"))
              .withColumn("week_of_year", F.weekofyear("date"))
              .withColumn("is_weekend", F.weekday("date") >= 5))
