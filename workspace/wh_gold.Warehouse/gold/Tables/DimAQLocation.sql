CREATE TABLE [gold].[DimAQLocation] (
    [LocationKey]  BIGINT        NOT NULL,
    [LocationName] VARCHAR (200) NULL,
    [Latitude]     FLOAT (53)    NULL,
    [Longitude]    FLOAT (53)    NULL,
    [Borough]      VARCHAR (30)  NULL
);


GO