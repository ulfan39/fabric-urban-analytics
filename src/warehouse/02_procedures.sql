/* =====================================================================
   wh_gold - load procedures                           02_procedures.sql
   Source: silver lakehouse lh_silver, read with three-part names
   (lh_silver.dbo.<table>) through its SQL analytics endpoint.
   Every procedure is idempotent (full rebuild of its table).
   ===================================================================== */

CREATE OR ALTER PROCEDURE gold.usp_load_DimDate AS
BEGIN
    TRUNCATE TABLE gold.DimDate;
    INSERT INTO gold.DimDate
    SELECT date_key, [date], [year], [quarter], [month], month_name, year_month, [day],
           day_of_week, day_name, week_of_year, CAST(is_weekend AS bit)
    FROM lh_silver.dbo.calendar;
END;
GO

CREATE OR ALTER PROCEDURE gold.usp_load_DimZone AS
BEGIN
    TRUNCATE TABLE gold.DimZone;
    INSERT INTO gold.DimZone (ZoneKey, Borough, Zone, ServiceZone)
    SELECT location_id, borough, zone, service_zone FROM lh_silver.dbo.taxi_zones;
END;
GO

CREATE OR ALTER PROCEDURE gold.usp_load_DimFX AS
BEGIN
    TRUNCATE TABLE gold.DimFX;
    INSERT INTO gold.DimFX (DateKey, [Date], UsdPerEur, EurPerUsd, IsPublished)
    SELECT CONVERT(int, CONVERT(char(8), [date], 112)), [date], usd_per_eur, eur_per_usd, CAST(is_published AS bit)
    FROM lh_silver.dbo.fx_daily
    WHERE usd_per_eur IS NOT NULL;
END;
GO

CREATE OR ALTER PROCEDURE gold.usp_load_DimGDP AS
BEGIN
    TRUNCATE TABLE gold.DimGDP;
    INSERT INTO gold.DimGDP (CountryCode, CountryName, [Year], GdpUsd, GdpGrowthPct)
    SELECT country_code, country_name, [year], gdp_usd,
           100.0 * (gdp_usd / NULLIF(LAG(gdp_usd) OVER (PARTITION BY country_code ORDER BY [year]), 0) - 1)
    FROM lh_silver.dbo.gdp_yearly;
END;
GO

CREATE OR ALTER PROCEDURE gold.usp_load_DimAQLocation AS
BEGIN
    TRUNCATE TABLE gold.DimAQLocation;
    INSERT INTO gold.DimAQLocation (LocationKey, LocationName, Latitude, Longitude, Borough)
    SELECT location_id, MAX(location_name), MAX(latitude), MAX(longitude), MAX(borough)
    FROM lh_silver.dbo.air_quality_daily
    GROUP BY location_id;
END;
GO

CREATE OR ALTER PROCEDURE gold.usp_load_FactTaxiDaily AS
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

CREATE OR ALTER PROCEDURE gold.usp_load_FactTaxiHourly AS
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

CREATE OR ALTER PROCEDURE gold.usp_load_FactAirQualityDaily AS
BEGIN
    TRUNCATE TABLE gold.FactAirQualityDaily;
    INSERT INTO gold.FactAirQualityDaily
        (DateKey, LocationKey, SensorId, Parameter, Units, AvgValue, MinValue, MaxValue, CoveragePct)
    SELECT CONVERT(int, CONVERT(char(8), [date], 112)), location_id, sensor_id, parameter, units,
           value_avg, value_min, value_max, coverage_pct
    FROM lh_silver.dbo.air_quality_daily;
END;
GO

/* Runs every enabled procedure listed in meta.GoldLoads (in LoadOrder) and logs it.
   New fact/dimension = new procedure + one row in meta.GoldLoads; this procedure does not change. */
CREATE OR ALTER PROCEDURE gold.usp_load_all @RunId varchar(64) = NULL AS
BEGIN
    DECLARE @order int = (SELECT MIN(LoadOrder) FROM meta.GoldLoads WHERE Enabled = 1);
    DECLARE @proc varchar(128), @started datetime2(6), @sql varchar(300);
    WHILE @order IS NOT NULL
    BEGIN
        SELECT @proc = ProcName FROM meta.GoldLoads WHERE LoadOrder = @order;
        SET @started = SYSUTCDATETIME();
        BEGIN TRY
            SET @sql = 'EXEC ' + @proc;
            EXEC (@sql);
            INSERT INTO meta.LoadHistory (RunId, ProcName, Status, StartedAt, FinishedAt)
            VALUES (@RunId, @proc, 'succeeded', @started, SYSUTCDATETIME());
        END TRY
        BEGIN CATCH
            INSERT INTO meta.LoadHistory (RunId, ProcName, Status, Message, StartedAt, FinishedAt)
            VALUES (@RunId, @proc, 'failed', LEFT(ERROR_MESSAGE(), 4000), @started, SYSUTCDATETIME());
            THROW;
        END CATCH;
        SET @order = (SELECT MIN(LoadOrder) FROM meta.GoldLoads WHERE Enabled = 1 AND LoadOrder > @order);
    END;
END;
GO
