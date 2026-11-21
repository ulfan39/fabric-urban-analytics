CREATE   PROCEDURE gold.usp_load_FactTaxiDaily AS
BEGIN
    TRUNCATE TABLE gold.FactTaxiDaily;
    WITH agg AS (
        SELECT pickup_date, pu_location_id, service,
               COUNT(*)                                   AS Trips,
               SUM(passenger_count)                       AS Passengers,
               SUM(trip_distance)                         AS DistanceMiles,
               SUM(fare_amount)                           AS FareUsd,
               SUM(tip_amount)                            AS TipUsd,
               SUM(total_amount)                          AS TotalUsd,
               SUM(duration_min)                          AS DurationMin,
               SUM(CASE WHEN airport_fee > 0 THEN 1 ELSE 0 END) AS AirportTrips
        FROM lh_silver.dbo.taxi_trips
        GROUP BY pickup_date, pu_location_id, service
    )
    INSERT INTO gold.FactTaxiDaily
    SELECT CONVERT(int, CONVERT(char(8), a.pickup_date, 112)), a.pu_location_id, a.service,
           a.Trips, a.Passengers, a.DistanceMiles, a.FareUsd, a.TipUsd, a.TotalUsd,
           a.TotalUsd * fx.eur_per_usd, a.DurationMin, a.AirportTrips
    FROM agg a
    LEFT JOIN lh_silver.dbo.fx_daily fx ON fx.[date] = a.pickup_date;
END;

GO