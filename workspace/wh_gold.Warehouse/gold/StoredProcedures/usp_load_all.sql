CREATE   PROCEDURE gold.usp_load_all @RunId varchar(64) = NULL AS
BEGIN
    -- Fabric Warehouse does not allow variables inside table queries, so the list in
    -- meta.GoldLoads is turned into one script (one logged TRY/CATCH block per procedure).
    DECLARE @sql varchar(8000) = (
        SELECT STRING_AGG(CAST(
              'INSERT INTO meta.LoadHistory (RunId, ProcName, Status, StartedAt) '
            + 'VALUES ({RUN}, ''' + ProcName + ''', ''running'', SYSUTCDATETIME()); '
            + 'BEGIN TRY EXEC ' + ProcName + '; '
            + 'UPDATE meta.LoadHistory SET Status = ''succeeded'', FinishedAt = SYSUTCDATETIME() '
            + 'WHERE ProcName = ''' + ProcName + ''' AND Status = ''running''; END TRY '
            + 'BEGIN CATCH UPDATE meta.LoadHistory SET Status = ''failed'', Message = LEFT(ERROR_MESSAGE(), 4000), '
            + 'FinishedAt = SYSUTCDATETIME() WHERE ProcName = ''' + ProcName + ''' AND Status = ''running''; '
            + 'THROW; END CATCH;' AS varchar(1000)), ' ') WITHIN GROUP (ORDER BY LoadOrder)
        FROM meta.GoldLoads
        WHERE Enabled = 1);
    SET @sql = REPLACE(@sql, '{RUN}', COALESCE('''' + REPLACE(@RunId, '''', '') + '''', 'NULL'));
    EXEC (@sql);
END;

GO