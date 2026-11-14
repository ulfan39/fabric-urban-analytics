CREATE   VIEW gold.vw_RevenueFxDaily AS
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