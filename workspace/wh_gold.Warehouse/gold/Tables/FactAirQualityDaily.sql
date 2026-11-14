CREATE TABLE [gold].[FactAirQualityDaily] (
    [DateKey]     INT             NOT NULL,
    [LocationKey] BIGINT          NOT NULL,
    [SensorId]    BIGINT          NOT NULL,
    [Parameter]   VARCHAR (10)    NOT NULL,
    [Units]       VARCHAR (10)    NOT NULL,
    [AvgValue]    DECIMAL (12, 3) NULL,
    [MinValue]    DECIMAL (12, 3) NULL,
    [MaxValue]    DECIMAL (12, 3) NULL,
    [CoveragePct] DECIMAL (6, 2)  NULL
);


GO