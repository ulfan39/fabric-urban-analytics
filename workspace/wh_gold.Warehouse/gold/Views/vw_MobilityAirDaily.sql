CREATE   VIEW gold.vw_MobilityAirDaily AS
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