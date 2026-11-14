CREATE TABLE [gold].[DimGDP] (
    [CountryCode]  VARCHAR (3)     NOT NULL,
    [CountryName]  VARCHAR (100)   NULL,
    [Year]         SMALLINT        NOT NULL,
    [GdpUsd]       DECIMAL (20, 2) NOT NULL,
    [GdpGrowthPct] DECIMAL (9, 4)  NULL
);


GO