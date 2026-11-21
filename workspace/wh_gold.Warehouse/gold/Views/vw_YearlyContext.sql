CREATE   VIEW gold.vw_YearlyContext AS
SELECT y.[Year],
       y.Trips, y.TotalUsd,
       (SELECT AVG(a.AvgValue) FROM gold.FactAirQualityDaily a WHERE a.Parameter = 'pm25' AND a.DateKey / 10000 = y.[Year]) AS AvgPM25,
       (SELECT AVG(a.AvgValue) FROM gold.FactAirQualityDaily a WHERE a.Parameter = 'no2'  AND a.DateKey / 10000 = y.[Year]) AS AvgNO2,
       g.GdpUsd AS UsGdpUsd, g.GdpGrowthPct AS UsGdpGrowthPct
FROM (SELECT f.DateKey / 10000 AS [Year], SUM(f.Trips) AS Trips, SUM(f.TotalUsd) AS TotalUsd
      FROM gold.FactTaxiDaily f GROUP BY f.DateKey / 10000) y
LEFT JOIN gold.DimGDP g ON g.CountryCode = 'USA' AND g.[Year] = y.[Year];

GO