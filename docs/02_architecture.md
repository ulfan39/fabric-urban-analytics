# 2. Architecture and lineage

## Layers

| layer | store | content | written by |
|---|---|---|---|
| **Bronze** (raw) | `lh_bronze` Files | taxi Parquet files, zone CSV, weather JSON - unchanged copies, partitioned `year=/month=` | `pl_bronze_files` (Copy), `nb_bronze_http` |
| | `lh_bronze` Tables | `openaq_sensor_days`, `worldbank_gdp`, `ecb_fx` - API JSON/CSV flattened to tables, all columns as delivered + `ingested_at` | Dataflows Gen2 |
| **Silver** (clean) | `lh_silver` Delta tables | typed, de-duplicated, standardised, enriched with date parts; `_load_log`; `calendar` | `nb_silver_load` + `nb_transforms` |
| **Gold** (model) | `wh_gold` Warehouse | star schema (facts by day), analytical views, load metadata | `gold.usp_load_all` |
| Consumption | Power BI semantic model (Direct Lake on `wh_gold`) | four report pages | - |

## Lineage

```mermaid
flowchart TB
    tlc[TLC trip-data/*.parquet] --> b1[lh_bronze Files raw/nyc_taxi/yellow]
    zl[TLC taxi_zone_lookup.csv] --> b2[lh_bronze Files raw/nyc_taxi/zones]
    oaq[OpenAQ /v3/locations + /v3/sensors/id/days] --> b3[lh_bronze.openaq_sensor_days]
    wb[World Bank NY.GDP.MKTP.CD] --> b4[lh_bronze.worldbank_gdp]
    ecb[ECB EXR D.USD.EUR.SP00.A] --> b5[lh_bronze.ecb_fx]
    b1 --> s1[lh_silver.taxi_trips]
    b2 --> s2[lh_silver.taxi_zones]
    b3 --> s3[lh_silver.air_quality_daily]
    b4 --> s4[lh_silver.gdp_yearly]
    b5 --> s5[lh_silver.fx_daily]
    s1 & s5 --> g1[FactTaxiDaily]
    s1 & s2 --> g2[FactTaxiHourly]
    s3 --> g3[FactAirQualityDaily]
    s3 --> g4[DimAQLocation]
    s2 --> g5[DimZone]
    s5 --> g6[DimFX]
    s4 --> g7[DimGDP]
    cal[lh_silver.calendar] --> g8[DimDate]
    g1 & g2 & g3 & g4 & g5 & g6 & g7 & g8 --> v[views + Power BI]
```

Fabric's own lineage view (workspace > Lineage) shows the same item-level graph; Purview (optional) adds column level.

## Orchestration

`pl_master` (daily 06:00): bronze files ∥ three dataflows → silver notebook → wait → gold procedure → semantic model refresh.
Every step is idempotent, so a failed run is simply re-run.

## Design decisions

| decision | why |
|---|---|
| One configuration file in Git read at run time by notebooks **and** dataflows | single source of truth; adding/changing a source is a reviewed commit, not a UI change in several places |
| Pipeline plans its own work (`nb_bronze_plan_files` → ForEach Copy) | metadata-driven: new file datasets need no pipeline change; only missing months are copied |
| Bronze keeps raw files unchanged | re-processing is always possible, audit trail |
| Each monthly taxi file is read alone and conformed to one schema | TLC changed column names/types over time (`Airport_fee`/`airport_fee`, int/double, `cbd_congestion_fee` from 2025) |
| `_load_log` with bronze file + modification time | incremental: only new or re-downloaded files are processed; monitoring of rejected rows |
| `replace_partition` (taxi), `merge` (air quality, weather), `overwrite` (small reference data) | idempotent loads matching the change pattern of each source |
| FX forward-filled to every calendar day, flag `is_published` | ECB has no rates on weekends/holidays; taxi revenue exists every day |
| Units standardised in silver (NO2 → ppb) | OpenAQ sensors report NO2 in ppm or µg/m³ |
| Gold in Warehouse, loads listed in `meta.GoldLoads` | T-SQL star schema for BI; new facts are added by registration, the orchestrating procedure stays unchanged |
| Secrets only in `lh_bronze.cfg_secrets` (restricted) | no keys in Git; production: Azure Key Vault |
