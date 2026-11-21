CREATE TABLE [gold].[FactTaxiDaily] (
    [DateKey]       INT             NOT NULL,
    [PickupZoneKey] INT             NOT NULL,
    [Service]       VARCHAR (10)    NOT NULL,
    [Trips]         INT             NOT NULL,
    [Passengers]    INT             NULL,
    [DistanceMiles] DECIMAL (18, 2) NULL,
    [FareUsd]       DECIMAL (18, 2) NULL,
    [TipUsd]        DECIMAL (18, 2) NULL,
    [TotalUsd]      DECIMAL (18, 2) NULL,
    [TotalEur]      DECIMAL (18, 2) NULL,
    [DurationMin]   DECIMAL (18, 2) NULL,
    [AirportTrips]  INT             NULL
);


GO