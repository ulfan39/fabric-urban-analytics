CREATE TABLE [meta].[LoadHistory] (
    [RunId]      VARCHAR (64)   NULL,
    [ProcName]   VARCHAR (128)  NOT NULL,
    [Status]     VARCHAR (20)   NOT NULL,
    [Message]    VARCHAR (4000) NULL,
    [StartedAt]  DATETIME2 (6)  NOT NULL,
    [FinishedAt] DATETIME2 (6)  NULL
);


GO