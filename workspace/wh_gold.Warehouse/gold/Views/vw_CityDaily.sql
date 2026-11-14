CREATE   VIEW gold.vw_CityDaily AS
SELECT d.[Date], d.DateKey, d.YearMonth, d.DayName, d.IsWeekend,
       (SELECT SUM(Trips) FROM gold.FactTaxiDaily f WHERE f.DateKey = d.DateKey) AS Trips,
       (SELECT AVG(AvgValue) FROM gold.FactAirQualityDaily a WHERE a.DateKey = d.DateKey AND a.Parameter = 'pm25') AS PM25,
       (SELECT AVG(AvgValue) FROM gold.FactAirQualityDaily a WHERE a.DateKey = d.DateKey AND a.Parameter = 'no2')  AS NO2
FROM gold.DimDate d
WHERE EXISTS (SELECT 1 FROM gold.FactTaxiDaily f WHERE f.DateKey = d.DateKey);

GO