/* =====================================================================
   wh_gold - star schema (Gold layer)                     01_tables.sql
   Run once in the warehouse wh_gold (New SQL query > paste > Run).
   Fabric Warehouse notes: varchar (UTF-8) instead of nvarchar, datetime2(6),
   keys are logical (not enforced) - integrity is guaranteed by the load procedures.
   ===================================================================== */
IF SCHEMA_ID('gold') IS NULL EXEC('CREATE SCHEMA gold');
IF SCHEMA_ID('meta') IS NULL EXEC('CREATE SCHEMA meta');
GO

-- ---------------------------------------------------------------- dimensions
DROP TABLE IF EXISTS gold.DimDate;
CREATE TABLE gold.DimDate (
    DateKey     int          NOT NULL,   -- yyyymmdd
    [Date]      date         NOT NULL,
    [Year]      smallint     NOT NULL,
    [Quarter]   smallint     NOT NULL,
    [Month]     smallint     NOT NULL,
    MonthName   varchar(10)  NOT NULL,
    YearMonth   varchar(7)   NOT NULL,
    [Day]       smallint     NOT NULL,
    DayOfWeek   smallint     NOT NULL,   -- 1 = Monday ... 7 = Sunday
    DayName     varchar(10)  NOT NULL,
    WeekOfYear  smallint     NOT NULL,
    IsWeekend   bit          NOT NULL
);

DROP TABLE IF EXISTS gold.DimZone;
CREATE TABLE gold.DimZone (
    ZoneKey     int          NOT NULL,   -- = TLC LocationID
    Borough     varchar(30)  NULL,
    Zone        varchar(100) NULL,
    ServiceZone varchar(30)  NULL
);

DROP TABLE IF EXISTS gold.DimAQLocation;
CREATE TABLE gold.DimAQLocation (
    LocationKey  bigint       NOT NULL,  -- = OpenAQ location id
    LocationName varchar(200) NULL,
    Latitude     float        NULL,
    Longitude    float        NULL,
    Borough      varchar(30)  NULL       -- approximated in silver (nearest borough centre)
);

DROP TABLE IF EXISTS gold.DimFX;
CREATE TABLE gold.DimFX (
    DateKey     int           NOT NULL,
    [Date]      date          NOT NULL,
    UsdPerEur   decimal(12,6) NOT NULL,  -- ECB reference rate
    EurPerUsd   decimal(12,6) NOT NULL,
    IsPublished bit           NOT NULL   -- 0 = weekend/holiday, last published rate carried forward
);

DROP TABLE IF EXISTS gold.DimGDP;
CREATE TABLE gold.DimGDP (
    CountryCode  varchar(3)     NOT NULL,
    CountryName  varchar(100)   NULL,
    [Year]       smallint       NOT NULL,
    GdpUsd       decimal(20,2)  NOT NULL,
    GdpGrowthPct decimal(9,4)   NULL      -- nominal growth vs previous year
);

-- ---------------------------------------------------------------- facts
DROP TABLE IF EXISTS gold.FactTaxiDaily;
CREATE TABLE gold.FactTaxiDaily (           -- grain: day x pickup zone x service
    DateKey        int            NOT NULL,
    PickupZoneKey  int            NOT NULL,
    Service        varchar(10)    NOT NULL,
    Trips          int            NOT NULL,
    Passengers     int            NULL,
    DistanceMiles  decimal(18,2)  NULL,
    FareUsd        decimal(18,2)  NULL,
    TipUsd         decimal(18,2)  NULL,
    TotalUsd       decimal(18,2)  NULL,
    TotalEur       decimal(18,2)  NULL,      -- TotalUsd * EurPerUsd of the trip date
    DurationMin    decimal(18,2)  NULL,      -- sum, for weighted averages
    AirportTrips   int            NULL
);

DROP TABLE IF EXISTS gold.FactTaxiHourly;
CREATE TABLE gold.FactTaxiHourly (          -- grain: day x hour x pickup borough (time-of-day analysis)
    DateKey        int            NOT NULL,
    [Hour]         smallint       NOT NULL,
    Borough        varchar(30)    NOT NULL,
    Trips          int            NOT NULL,
    TotalUsd       decimal(18,2)  NULL
);

DROP TABLE IF EXISTS gold.FactAirQualityDaily;
CREATE TABLE gold.FactAirQualityDaily (     -- grain: day x sensor
    DateKey      int            NOT NULL,
    LocationKey  bigint         NOT NULL,
    SensorId     bigint         NOT NULL,
    Parameter    varchar(10)    NOT NULL,   -- pm25 | no2
    Units        varchar(10)    NOT NULL,   -- ug/m3 | ppb (standardised in silver)
    AvgValue     decimal(12,3)  NULL,
    MinValue     decimal(12,3)  NULL,
    MaxValue     decimal(12,3)  NULL,
    CoveragePct  decimal(6,2)   NULL
);

-- ---------------------------------------------------------------- metadata (extensibility + monitoring)
DROP TABLE IF EXISTS meta.GoldLoads;
CREATE TABLE meta.GoldLoads (              -- which load procedures gold.usp_load_all runs, in which order
    LoadOrder int          NOT NULL,
    ProcName  varchar(128) NOT NULL,
    Enabled   bit          NOT NULL
);

DROP TABLE IF EXISTS meta.LoadHistory;
CREATE TABLE meta.LoadHistory (
    RunId      varchar(64)  NULL,
    ProcName   varchar(128) NOT NULL,
    Status     varchar(20)  NOT NULL,
    Message    varchar(4000) NULL,
    StartedAt  datetime2(6) NOT NULL,
    FinishedAt datetime2(6) NULL
);

INSERT INTO meta.GoldLoads (LoadOrder, ProcName, Enabled) VALUES
 (10, 'gold.usp_load_DimDate',             1),
 (20, 'gold.usp_load_DimZone',             1),
 (30, 'gold.usp_load_DimFX',               1),
 (40, 'gold.usp_load_DimGDP',              1),
 (50, 'gold.usp_load_DimAQLocation',       1),
 (60, 'gold.usp_load_FactTaxiDaily',       1),
 (70, 'gold.usp_load_FactTaxiHourly',      1),
 (80, 'gold.usp_load_FactAirQualityDaily', 1);
