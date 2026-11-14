CREATE   PROCEDURE gold.usp_load_DimGDP AS
BEGIN
    TRUNCATE TABLE gold.DimGDP;
    INSERT INTO gold.DimGDP (CountryCode, CountryName, [Year], GdpUsd, GdpGrowthPct)
    SELECT country_code, country_name, [year], gdp_usd,
           100.0 * (gdp_usd / NULLIF(LAG(gdp_usd) OVER (PARTITION BY country_code ORDER BY [year]), 0) - 1)
    FROM lh_silver.dbo.gdp_yearly;
END;

GO