/* =====================================================================
   wh_gold - analytical views (answer the key questions)   03_views.sql
   ===================================================================== */

-- Q1/Q2: traffic intensity vs air quality, per borough and day
CREATE OR ALTER VIEW gold.vw_MobilityAirDaily AS
WITH taxi AS (
    SELECT f.DateKey, z.Borough, SUM(f.Trips) AS Trips, SUM(f.TotalUsd) AS TotalUsd
    FROM gold.FactTaxiDaily f JOIN gold.DimZone z ON z.ZoneKey = f.PickupZoneKey
    GROUP BY f.DateKey, z.Borough
), air AS (
    SELECT a.DateKey, l.Borough,
           AVG(CASE WHEN a.Parameter = 'pm25' THEN a.AvgValue END) AS PM25,
           AVG(CASE WHEN a.Parameter = 'no2'  THEN a.AvgValue END) AS NO2,
           COUNT(DISTINCT a.SensorId) AS Sensors
    FROM gold.FactAirQualityDaily a JOIN gold.DimAQLocation l ON l.LocationKey = a.LocationKey
    GROUP BY a.DateKey, l.Borough
)
SELECT d.[Date], d.DateKey, d.DayName, d.IsWeekend, t.Borough, t.Trips, t.TotalUsd, a.PM25, a.NO2, a.Sensors
FROM taxi t
JOIN gold.DimDate d ON d.DateKey = t.DateKey
LEFT JOIN air a ON a.DateKey = t.DateKey AND a.Borough = t.Borough;
GO

-- Q1: city-wide daily view (all boroughs together)
CREATE OR ALTER VIEW gold.vw_CityDaily AS
SELECT d.[Date], d.DateKey, d.YearMonth, d.DayName, d.IsWeekend,
       (SELECT SUM(Trips) FROM gold.FactTaxiDaily f WHERE f.DateKey = d.DateKey) AS Trips,
       (SELECT AVG(AvgValue) FROM gold.FactAirQualityDaily a WHERE a.DateKey = d.DateKey AND a.Parameter = 'pm25') AS PM25,
       (SELECT AVG(AvgValue) FROM gold.FactAirQualityDaily a WHERE a.DateKey = d.DateKey AND a.Parameter = 'no2')  AS NO2
FROM gold.DimDate d
WHERE EXISTS (SELECT 1 FROM gold.FactTaxiDaily f WHERE f.DateKey = d.DateKey);
GO

-- Q3: revenue per trip in USD and EUR with the exchange rate
CREATE OR ALTER VIEW gold.vw_RevenueFxDaily AS
SELECT d.[Date], d.DateKey, d.YearMonth,
       SUM(f.Trips) AS Trips, SUM(f.TotalUsd) AS TotalUsd, SUM(f.TotalEur) AS TotalEur,
       SUM(f.TotalUsd) / NULLIF(SUM(f.Trips), 0) AS RevenuePerTripUsd,
       SUM(f.TotalEur) / NULLIF(SUM(f.Trips), 0) AS RevenuePerTripEur,
       MAX(x.UsdPerEur) AS UsdPerEur, MAX(CAST(x.IsPublished AS int)) AS FxPublished
FROM gold.FactTaxiDaily f
JOIN gold.DimDate d ON d.DateKey = f.DateKey
LEFT JOIN gold.DimFX x ON x.DateKey = f.DateKey
GROUP BY d.[Date], d.DateKey, d.YearMonth;
GO

-- Q4: yearly growth context (mobility, environment, economy side by side)
CREATE OR ALTER VIEW gold.vw_YearlyContext AS
SELECT y.[Year],
       y.Trips, y.TotalUsd,
       (SELECT AVG(a.AvgValue) FROM gold.FactAirQualityDaily a WHERE a.Parameter = 'pm25' AND a.DateKey / 10000 = y.[Year]) AS AvgPM25,
       (SELECT AVG(a.AvgValue) FROM gold.FactAirQualityDaily a WHERE a.Parameter = 'no2'  AND a.DateKey / 10000 = y.[Year]) AS AvgNO2,
       g.GdpUsd AS UsGdpUsd, g.GdpGrowthPct AS UsGdpGrowthPct
FROM (SELECT f.DateKey / 10000 AS [Year], SUM(f.Trips) AS Trips, SUM(f.TotalUsd) AS TotalUsd
      FROM gold.FactTaxiDaily f GROUP BY f.DateKey / 10000) y
LEFT JOIN gold.DimGDP g ON g.CountryCode = 'USA' AND g.[Year] = y.[Year];
GO

-- monitoring: row counts of the gold tables
CREATE OR ALTER VIEW meta.vw_TableCounts AS
SELECT 'DimDate' AS TableName, COUNT_BIG(*) AS Row_Count FROM gold.DimDate
UNION ALL SELECT 'DimZone', COUNT_BIG(*) FROM gold.DimZone
UNION ALL SELECT 'DimAQLocation', COUNT_BIG(*) FROM gold.DimAQLocation
UNION ALL SELECT 'DimFX', COUNT_BIG(*) FROM gold.DimFX
UNION ALL SELECT 'DimGDP', COUNT_BIG(*) FROM gold.DimGDP
UNION ALL SELECT 'FactTaxiDaily', COUNT_BIG(*) FROM gold.FactTaxiDaily
UNION ALL SELECT 'FactTaxiHourly', COUNT_BIG(*) FROM gold.FactTaxiHourly
UNION ALL SELECT 'FactAirQualityDaily', COUNT_BIG(*) FROM gold.FactAirQualityDaily;
GO
