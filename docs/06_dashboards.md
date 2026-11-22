# 6. Dashboards (Power BI, Direct Lake)

Semantic model `sm_nyc_urban` and report `rpt_nyc_urban` are workspace items and are versioned in Git
(folder `workspace/`).

## Semantic model `sm_nyc_urban`
wh_gold > New semantic model > select the `gold` tables (Direct Lake: the model reads the warehouse Delta
tables directly, no import or scheduled refresh copy).

Relationships (many-to-one, single direction, dimension → fact, unless noted):

| from (many) | to (one) |
|---|---|
| FactTaxiDaily[DateKey], FactTaxiHourly[DateKey], FactAirQualityDaily[DateKey] | DimDate[DateKey] |
| FactTaxiDaily[PickupZoneKey] | DimZone[ZoneKey] |
| FactAirQualityDaily[LocationKey] | DimAQLocation[LocationKey] |
| DimFX[DateKey] | DimDate[DateKey] (one-to-one, both directions) |

* `DimDate` is marked as date table on `Date`; `DayName` is sorted by `DayOfWeek`.
* `DimGDP` has no relationship (yearly grain, 2000 onwards); measures join it on year with `TREATAS`.
* There are two `Borough` columns on purpose: `DimZone[Borough]` (taxi pickup zones) and
  `DimAQLocation[Borough]` (air quality stations, nearest-centroid approximation, includes New Jersey).
  A borough slicer on a taxi visual must use `DimZone[Borough]`.

## Measures (DAX)

Added in the DAX query view (*Update model with changes*). The base measure is called **Total Trips**, because
`Trips` is already a column name in `FactTaxiDaily`.

```DAX
Total Trips          = SUM ( FactTaxiDaily[Trips] )
Revenue USD          = SUM ( FactTaxiDaily[TotalUsd] )
Revenue EUR          = SUM ( FactTaxiDaily[TotalEur] )
Revenue per Trip USD = DIVIDE ( [Revenue USD], [Total Trips] )
Revenue per Trip EUR = DIVIDE ( [Revenue EUR], [Total Trips] )
Avg Fare USD         = DIVIDE ( SUM ( FactTaxiDaily[FareUsd] ), [Total Trips] )
Avg Duration min     = DIVIDE ( SUM ( FactTaxiDaily[DurationMin] ), [Total Trips] )
Trips per Day        = DIVIDE ( [Total Trips], DISTINCTCOUNT ( FactTaxiDaily[DateKey] ) )
PM2.5                = CALCULATE ( AVERAGE ( FactAirQualityDaily[AvgValue] ), FactAirQualityDaily[Parameter] = "pm25" )
NO2                  = CALCULATE ( AVERAGE ( FactAirQualityDaily[AvgValue] ), FactAirQualityDaily[Parameter] = "no2" )
USD per EUR          = AVERAGE ( DimFX[UsdPerEur] )
US GDP USD           = CALCULATE ( SUM ( DimGDP[GdpUsd] ), DimGDP[CountryCode] = "USA",
                           TREATAS ( VALUES ( DimDate[Year] ), DimGDP[Year] ) )
Corr Trips PM2.5     =
    VAR T = FILTER ( ADDCOLUMNS ( VALUES ( DimDate[Date] ), "x", [Total Trips], "y", [PM2.5] ),
                     NOT ISBLANK ( [x] ) && NOT ISBLANK ( [y] ) )
    VAR mx = AVERAGEX ( T, [x] )
    VAR my = AVERAGEX ( T, [y] )
    RETURN DIVIDE ( SUMX ( T, ( [x] - mx ) * ( [y] - my ) ),
                    SQRT ( SUMX ( T, ( [x] - mx ) ^ 2 ) * SUMX ( T, ( [y] - my ) ^ 2 ) ) )
```
(`Corr Trips NO2` is the same with `[NO2]`. It is the Pearson correlation over the days on which both
values exist.)

Formats (model > measure > Properties > Formatting): USD measures currency `$`, EUR measures currency `€`,
PM2.5 / NO2 decimal with 1 place, correlations decimal with 2 places, USD per EUR decimal with 4 places.

## Report `rpt_nyc_urban`

A date slicer (`DimDate[Date]`, *Between*) is synced across all four pages (View > Sync slicers). Each copy has
a visual filter `DimDate[Year]` 2025-2026, because the calendar covers 2000-2027 for the GDP history.

| page | visuals | answers |
|---|---|---|
| **Mobility** | cards Total Trips, Revenue USD, Avg Fare USD, Avg Duration min; line Total Trips by Date; bar Total Trips by pickup zone; matrix DayName × Hour (FactTaxiHourly); slicers date, borough (`DimZone`) | peak times and zones, trend |
| **Air Quality** | cards PM2.5, NO2; line PM2.5 and NO2 by Date; bar PM2.5 / NO2 by borough; table of stations ranked by PM2.5; note on the 16 Jul 2026 wildfire smoke | hotspots by location and time |
| **Mobility vs Air** | combo chart Total Trips (columns) + PM2.5 / NO2 (lines) by Date; scatter Total Trips vs NO2, one dot per day, with trend line; cards Corr Trips NO2 / PM2.5; conclusion text | Q1, Q2 |
| **Economy** | cards Revenue per Trip USD / EUR, USD per EUR; line Revenue per Trip USD and EUR by Date with USD per EUR on the secondary axis; line GDP by country and year; matrix by Year (Total Trips, Revenue USD, PM2.5, NO2, US GDP USD - not filtered by the date slicer) | Q3, Q4 |

## Findings

| question | finding |
|---|---|
| Q1 traffic vs air quality | Daily city-wide taxi trips and NO2 show a weak positive relationship (rising but flat trend line, wide scatter). PM2.5 is driven mainly by regional events and does not follow taxi traffic. |
| Q2 zones and times | Taxi demand peaks on weekday afternoons and evenings and in Midtown / Upper East Side and at JFK. Air quality is available per day and station, not per hour, so the link can only be studied at day × borough level (`gold.vw_MobilityAirDaily`). |
| Q3 revenue in USD vs EUR | Revenue per trip about $31.0 / €27.0 (Jun-Oct 2026). Average fare alone is about $22; the rest is tips, tolls, surcharges and taxes. The EUR value moves with the daily ECB rate even when USD fares do not change. |
| Q4 multi-year growth | US GDP grows from 2000 to 2025 in the matrix (with a dip in 2020), to about $30.8 trillion in 2025. Taxi data currently covers 2026 only, so mobility growth over years cannot be measured yet; it needs only an earlier `start_date` (see [05_adding_a_source.md](05_adding_a_source.md)). |

Notable event: on **16 Jul 2026** PM2.5 reached 86.8 µg/m³ (about ten times the average of 8.5) while NO2 stayed
normal (17.0 ppb). NYC Emergency Management and NY DEC issued air quality advisories for smoke from Canadian
wildfires on 14-19 Jul 2026. NO2 is therefore the better indicator of traffic emissions.

Limitations: only yellow taxis (a small part of all vehicles); no weather data (wind and temperature control NO2
concentration); air quality is daily. Adding weather (`weather_nyc_daily`, already in the configuration,
disabled) is the next extension.

Optional RLS (Phase 5): Manage roles > one role per borough, e.g. `Manhattan` with table filter
`DimZone[Borough] = "Manhattan"`; assign users/groups to the roles in the semantic model security settings.
