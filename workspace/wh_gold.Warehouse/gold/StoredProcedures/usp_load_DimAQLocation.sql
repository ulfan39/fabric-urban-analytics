CREATE   PROCEDURE gold.usp_load_DimAQLocation AS
BEGIN
    TRUNCATE TABLE gold.DimAQLocation;
    INSERT INTO gold.DimAQLocation (LocationKey, LocationName, Latitude, Longitude, Borough)
    SELECT location_id, MAX(location_name), MAX(latitude), MAX(longitude), MAX(borough)
    FROM lh_silver.dbo.air_quality_daily
    GROUP BY location_id;
END;

GO