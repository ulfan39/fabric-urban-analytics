CREATE TABLE [gold].[DimFX] (
    [DateKey]     INT             NOT NULL,
    [Date]        DATE            NOT NULL,
    [UsdPerEur]   DECIMAL (12, 6) NOT NULL,
    [EurPerUsd]   DECIMAL (12, 6) NOT NULL,
    [IsPublished] BIT             NOT NULL
);


GO