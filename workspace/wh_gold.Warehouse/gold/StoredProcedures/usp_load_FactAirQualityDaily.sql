CREATE   PROCEDURE gold.usp_load_FactAirQualityDaily AS
BEGIN
    TRUNCATE TABLE gold.FactAirQualityDaily;
    INSERT INTO gold.FactAirQualityDaily
        (DateKey, LocationKey, SensorId, Parameter, Units, AvgValue, MinValue, MaxValue, CoveragePct)
    SELECT CONVERT(int, CONVERT(char(8), [date], 112)), location_id, sensor_id, parameter, units,
           value_avg, value_min, value_max, coverage_pct
    FROM lh_silver.dbo.air_quality_daily;
END;

GO