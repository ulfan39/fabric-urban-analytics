CREATE   PROCEDURE gold.usp_load_DimZone AS
BEGIN
    TRUNCATE TABLE gold.DimZone;
    INSERT INTO gold.DimZone (ZoneKey, Borough, Zone, ServiceZone)
    SELECT location_id, borough, zone, service_zone FROM lh_silver.dbo.taxi_zones;
END;

GO