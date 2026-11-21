CREATE   PROCEDURE gold.usp_load_DimFX AS
BEGIN
    TRUNCATE TABLE gold.DimFX;
    INSERT INTO gold.DimFX (DateKey, [Date], UsdPerEur, EurPerUsd, IsPublished)
    SELECT CONVERT(int, CONVERT(char(8), [date], 112)), [date], usd_per_eur, eur_per_usd, CAST(is_published AS bit)
    FROM lh_silver.dbo.fx_daily
    WHERE usd_per_eur IS NOT NULL;
END;

GO