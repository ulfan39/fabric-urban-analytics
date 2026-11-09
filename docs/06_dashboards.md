# 6. Dashboards (Power BI, Direct Lake)

## Semantic model `sm_nyc_urban`
wh_gold > New semantic model > select the `gold` tables.

Relationships (single direction, dimension → fact):

| from | to |
|---|---|
| DimDate[DateKey] 1 | * FactTaxiDaily[DateKey], FactTaxiHourly[DateKey], FactAirQualityDaily[DateKey], DimFX[DateKey] (1:1) |
| DimZone[ZoneKey] 1 | * FactTaxiDaily[PickupZoneKey] |
| DimAQLocation[LocationKey] 1 | * FactAirQualityDaily[LocationKey] |

Mark `DimDate` as date table. `DimGDP` is joined on year in measures (different grain).

## Measures (DAX)

```DAX
Trips              = SUM ( FactTaxiDaily[Trips] )
Revenue USD        = SUM ( FactTaxiDaily[TotalUsd] )
Revenue EUR        = SUM ( FactTaxiDaily[TotalEur] )
Revenue per Trip USD = DIVIDE ( [Revenue USD], [Trips] )
Revenue per Trip EUR = DIVIDE ( [Revenue EUR], [Trips] )
Avg Fare USD       = DIVIDE ( SUM ( FactTaxiDaily[FareUsd] ), [Trips] )
Avg Duration min   = DIVIDE ( SUM ( FactTaxiDaily[DurationMin] ), [Trips] )
Trips per Day      = DIVIDE ( [Trips], DISTINCTCOUNT ( FactTaxiDaily[DateKey] ) )
PM2.5              = CALCULATE ( AVERAGE ( FactAirQualityDaily[AvgValue] ), FactAirQualityDaily[Parameter] = "pm25" )
NO2                = CALCULATE ( AVERAGE ( FactAirQualityDaily[AvgValue] ), FactAirQualityDaily[Parameter] = "no2" )
USD per EUR        = AVERAGE ( DimFX[UsdPerEur] )
FX effect EUR      = [Revenue EUR] - [Revenue USD] / CALCULATE ( AVERAGE ( DimFX[UsdPerEur] ), ALL ( DimDate ) )
US GDP USD         = CALCULATE ( SUM ( DimGDP[GdpUsd] ), DimGDP[CountryCode] = "USA",
                         TREATAS ( VALUES ( DimDate[Year] ), DimGDP[Year] ) )
Corr Trips PM2.5   =
    VAR T = FILTER ( ADDCOLUMNS ( VALUES ( DimDate[Date] ), "x", [Trips], "y", [PM2.5] ),
                     NOT ISBLANK ( [x] ) && NOT ISBLANK ( [y] ) )
    VAR n = COUNTROWS ( T )
    VAR mx = AVERAGEX ( T, [x] )
    VAR my = AVERAGEX ( T, [y] )
    RETURN DIVIDE ( SUMX ( T, ( [x] - mx ) * ( [y] - my ) ),
                    SQRT ( SUMX ( T, ( [x] - mx ) ^ 2 ) * SUMX ( T, ( [y] - my ) ^ 2 ) ) )
```
(`Corr Trips NO2` is the same with `[NO2]`.)

## Report pages

| page | visuals | answers |
|---|---|---|
| **Mobility** | KPI cards (Trips, Revenue USD, Avg Fare, Avg Duration); line Trips by Date; matrix Hour × DayName (FactTaxiHourly); bar top 10 pickup zones; slicers date, borough, service | peak times and zones, seasonality |
| **Air Quality** | line PM2.5 and NO2 by Date; map of DimAQLocation (bubble = PM2.5); bar by borough; slicer parameter | hotspots, seasonal variation |
| **Mobility vs Air** | combo chart Trips (columns) + PM2.5/NO2 (lines) by Date; scatter Trips vs NO2 per day (play axis month); cards Corr Trips PM2.5 / NO2; table from `vw_MobilityAirDaily` by borough | Q1, Q2 |
| **Economy** | line Revenue USD vs Revenue EUR by month + USD per EUR on secondary axis; cards Revenue per Trip USD/EUR, FX effect; column US GDP by year with Trips/Revenue | Q3, Q4 |

Optional RLS (Phase 5): Manage roles > one role per borough, e.g. `Manhattan` with table filter `DimZone[Borough] = "Manhattan"`; assign users/groups to the roles in the semantic model security settings.
