CREATE TABLE [gold].[DimDate] (
    [DateKey]    INT          NOT NULL,
    [Date]       DATE         NOT NULL,
    [Year]       SMALLINT     NOT NULL,
    [Quarter]    SMALLINT     NOT NULL,
    [Month]      SMALLINT     NOT NULL,
    [MonthName]  VARCHAR (10) NOT NULL,
    [YearMonth]  VARCHAR (7)  NOT NULL,
    [Day]        SMALLINT     NOT NULL,
    [DayOfWeek]  SMALLINT     NOT NULL,
    [DayName]    VARCHAR (10) NOT NULL,
    [WeekOfYear] SMALLINT     NOT NULL,
    [IsWeekend]  BIT          NOT NULL
);


GO