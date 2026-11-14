CREATE TABLE [gold].[FactTaxiHourly] (
    [DateKey]  INT             NOT NULL,
    [Hour]     SMALLINT        NOT NULL,
    [Borough]  VARCHAR (30)    NOT NULL,
    [Trips]    INT             NOT NULL,
    [TotalUsd] DECIMAL (18, 2) NULL
);


GO