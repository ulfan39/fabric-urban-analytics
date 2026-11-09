# 5. Adding a data source (extensibility)

The platform is built so that a new dataset is a **configuration change**, plus code only where the data has a
new shape. Three levels:

| level | example | what to change |
|---|---|---|
| A. same shape as an existing source | green taxi trips | `config/sources.json` only (`enabled: true`) |
| B. new shape, generic ingestion | Open-Meteo weather | config entry + one transform function |
| C. new gold fact/dimension | `FactWeatherDaily` | one table + one procedure + one row in `meta.GoldLoads` |

Nothing else changes: `pl_bronze_files`, `nb_bronze_http`, `nb_silver_load`, `gold.usp_load_all` and `pl_master`
pick the new source up automatically.

## A. Green taxi (configuration only)

The entry `nyc_taxi_green` already exists with `"enabled": false`. It uses the same transform `taxi_trips`
with other column names (`lpep_*`) passed as options:

```json
"silver": { "transform": "taxi_trips", "table": "taxi_trips",
            "options": { "service": "green", "pickup_col": "lpep_pickup_datetime", "dropoff_col": "lpep_dropoff_datetime" } }
```

Set `"enabled": true`, commit, run `pl_master`: the planner copies the green files, silver appends them to
`taxi_trips` with `service = 'green'`, `FactTaxiDaily` contains both services.

## B. Weather (new source, new shape)

1. **Bronze** - config entry with the generic HTTP method; URL and query come from config, `{month_start}`,
   `{month_end}`, `{yyyy}`, `{mm}` are filled per month:
   ```json
   { "name": "weather_nyc_daily", "enabled": true,
     "bronze": { "method": "notebook_http", "frequency": "monthly", "start_date": "2025-01-01",
                 "url": "https://archive-api.open-meteo.com/v1/archive",
                 "query": { "latitude": "40.7128", "longitude": "-74.0060",
                            "start_date": "{month_start}", "end_date": "{month_end}",
                            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,precipitation_sum,wind_speed_10m_max",
                            "timezone": "America/New_York" },
                 "landing_folder": "raw/weather/open_meteo/year={yyyy}/month={mm}",
                 "file_name": "weather_{yyyy}-{mm}.json" },
     "silver": { "transform": "weather_daily", "table": "weather_daily", "write_mode": "merge", "keys": ["date"] } }
   ```
2. **Silver** - one function in `nb_transforms` with the standard signature and one registry line:
   ```python
   def weather_daily(spark, lake, src, files):
       ...                      # JSON arrays -> one row per day
       return out, stats

   TRANSFORMS = { ..., "weather_daily": weather_daily }
   ```
3. Commit → `pl_master` → `lh_silver.weather_daily` exists. Both steps are covered by the unit tests.

## C. Gold

```sql
CREATE TABLE gold.FactWeatherDaily (DateKey int NOT NULL, TempMeanC decimal(5,2), PrecipMm decimal(7,2), WindMaxKmh decimal(6,2));
GO
CREATE OR ALTER PROCEDURE gold.usp_load_FactWeatherDaily AS
BEGIN
    TRUNCATE TABLE gold.FactWeatherDaily;
    INSERT INTO gold.FactWeatherDaily
    SELECT CONVERT(int, CONVERT(char(8), [date], 112)), temperature_2m_mean, precipitation_sum, wind_speed_10m_max
    FROM lh_silver.dbo.weather_daily;
END;
GO
INSERT INTO meta.GoldLoads VALUES (90, 'gold.usp_load_FactWeatherDaily', 1);
```

## API source with Dataflow Gen2

For a JSON/CSV API that should use a dataflow (like OpenAQ), copy one of `src/dataflows/*.pq`, change the source
name in `List.Select(Config[sources], each [name] = "...")`, add the config entry with `"method": "dataflow"` and
`"bronze_table"`, and add the Dataflow activity to `pl_master`. The silver side is the same as in B.

## Checklist

- [ ] config entry (name, enabled, bronze, silver)
- [ ] transform function + registry line (only for a new shape) + unit test with a small fixture
- [ ] gold table + procedure + `meta.GoldLoads` row (only if the data goes to the star schema)
- [ ] data dictionary entry
- [ ] pull request, tests green, merge, `Source control > Update` in Fabric
