CREATE   PROCEDURE gold.usp_load_FactTaxiHourly AS
BEGIN
    TRUNCATE TABLE gold.FactTaxiHourly;
    INSERT INTO gold.FactTaxiHourly (DateKey, [Hour], Borough, Trips, TotalUsd)
    SELECT CONVERT(int, CONVERT(char(8), t.pickup_date, 112)), t.pickup_hour, COALESCE(z.borough, 'Unknown'),
           COUNT(*), SUM(t.total_amount)
    FROM lh_silver.dbo.taxi_trips t
    LEFT JOIN lh_silver.dbo.taxi_zones z ON z.location_id = t.pu_location_id
    GROUP BY t.pickup_date, t.pickup_hour, COALESCE(z.borough, 'Unknown');
END;

GO