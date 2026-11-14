CREATE   VIEW meta.vw_TableCounts AS
SELECT 'DimDate' AS TableName, COUNT_BIG(*) AS Row_Count FROM gold.DimDate
UNION ALL SELECT 'DimZone', COUNT_BIG(*) FROM gold.DimZone
UNION ALL SELECT 'DimAQLocation', COUNT_BIG(*) FROM gold.DimAQLocation
UNION ALL SELECT 'DimFX', COUNT_BIG(*) FROM gold.DimFX
UNION ALL SELECT 'DimGDP', COUNT_BIG(*) FROM gold.DimGDP
UNION ALL SELECT 'FactTaxiDaily', COUNT_BIG(*) FROM gold.FactTaxiDaily
UNION ALL SELECT 'FactTaxiHourly', COUNT_BIG(*) FROM gold.FactTaxiHourly
UNION ALL SELECT 'FactAirQualityDaily', COUNT_BIG(*) FROM gold.FactAirQualityDaily;

GO