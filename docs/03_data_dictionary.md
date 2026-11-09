# 3. Data dictionary

## Bronze (`lh_bronze`)

| object | type | grain / content |
|---|---|---|
| `Files/raw/nyc_taxi/yellow/year=YYYY/month=MM/yellow_tripdata_YYYY-MM.parquet` | file | original TLC monthly file |
| `Files/raw/nyc_taxi/zones/taxi_zone_lookup.csv` | file | original zone lookup |
| `Files/raw/weather/open_meteo/year=YYYY/month=MM/weather_YYYY-MM.json` | file | Open-Meteo response (extension) |
| `Files/config/sources.json` | file | cached copy of the Git configuration |
| `openaq_sensor_days` | table | one row per sensor and day as returned by OpenAQ: location_id, location_name, latitude, longitude, sensor_id, parameter, units, date, value, min, max, coverage_pct, ingested_at |
| `worldbank_gdp` | table | country_code, country_name, indicator, year (text), value, ingested_at |
| `ecb_fx` | table | time_period (text date), obs_value (USD per EUR), currency, currency_denom, ingested_at |
| `cfg_secrets` | table | name, value - **restricted**, API keys |

## Silver (`lh_silver`)

### taxi_trips (partitioned by `year_month`)
| column | type | description |
|---|---|---|
| trip_id | string | sha256 of the natural key (deterministic surrogate key) |
| service | string | `yellow` / `green` |
| vendor_id | int | TPEP/LPEP provider |
| pickup_ts, dropoff_ts | timestamp | local NYC time as published |
| pickup_date, pickup_hour | date, int | enrichment (weekday etc. come from DimDate) |
| year_month | string | `YYYY-MM` of the source file |
| passenger_count | int | |
| trip_distance | double | miles |
| duration_min | double | dropoff - pickup |
| rate_code_id, store_and_fwd_flag, payment_type | int, string, int | TLC codes |
| pu_location_id, do_location_id | int | TLC zone ids (1-265) |
| fare_amount, extra, mta_tax, tip_amount, tolls_amount, improvement_surcharge, congestion_surcharge, airport_fee, cbd_congestion_fee, total_amount | double | USD; columns missing in a month are NULL |
| source_file, ingested_at | string, timestamp | audit |

Rejected rows (counted in `_load_log.rows_rejected`): missing timestamps, pickup outside the file's month,
duration ≤ 0 or > 360 min, distance < 0 or > 200 mi, negative fare/total, zone id outside 1-265. Duplicates on
(service, vendor, pickup, dropoff, PU, DO, distance, total) are removed.

### taxi_zones
location_id (int), borough, zone, service_zone, ingested_at.

### air_quality_daily (merge key sensor_id + date)
| column | description |
|---|---|
| sensor_id, location_id, location_name, latitude, longitude | OpenAQ identifiers and position |
| borough | nearest borough centre within 12 km; `New Jersey` west of the Hudson; else `Outside NYC` |
| parameter | `pm25` or `no2` |
| units_source / units | unit reported by the sensor / standard unit (`ug/m3` for PM2.5, `ppb` for NO2) |
| date | local day |
| value_avg, value_min, value_max | daily mean / min / max in the standard unit |
| coverage_pct | share of expected hourly values present |

### gdp_yearly
country_code (ISO3), country_name, year (int), gdp_usd (current USD), ingested_at.

### fx_daily (one row per calendar day)
date, usd_per_eur (ECB rate; carried forward on non-publication days), eur_per_usd, is_published, ingested_at.

### weather_daily (extension)
date, temperature_2m_max/min/mean (°C), precipitation_sum (mm), wind_speed_10m_max (km/h), ingested_at.

### calendar
date, date_key (yyyymmdd), year, quarter, month, month_name, year_month, day, day_of_week (1 = Monday), day_name, week_of_year, is_weekend.

### _load_log
run_id, source, bronze_file, bronze_modified, silver_table, rows_in, rows_out, rows_rejected, status, message, started_at, finished_at.

## Gold (`wh_gold`)

| table | grain | key columns | measures |
|---|---|---|---|
| `gold.FactTaxiDaily` | day × pickup zone × service | DateKey, PickupZoneKey, Service | Trips, Passengers, DistanceMiles, FareUsd, TipUsd, TotalUsd, **TotalEur** (TotalUsd × EurPerUsd of the day), DurationMin (sum), AirportTrips |
| `gold.FactTaxiHourly` | day × hour × pickup borough | DateKey, Hour, Borough | Trips, TotalUsd |
| `gold.FactAirQualityDaily` | day × sensor | DateKey, LocationKey, SensorId, Parameter | AvgValue, MinValue, MaxValue, CoveragePct (Units column) |
| `gold.DimDate` | day | DateKey | calendar attributes |
| `gold.DimZone` | TLC zone | ZoneKey (= LocationID) | Borough, Zone, ServiceZone |
| `gold.DimAQLocation` | OpenAQ location | LocationKey | LocationName, Latitude, Longitude, Borough |
| `gold.DimFX` | day | DateKey | UsdPerEur, EurPerUsd, IsPublished |
| `gold.DimGDP` | country × year | CountryCode, Year | GdpUsd, GdpGrowthPct |

Views: `gold.vw_MobilityAirDaily` (borough × day: trips, PM2.5, NO2), `gold.vw_CityDaily`, `gold.vw_RevenueFxDaily`,
`gold.vw_YearlyContext`; monitoring `meta.vw_TableCounts`, `meta.LoadHistory`, `meta.GoldLoads`.
