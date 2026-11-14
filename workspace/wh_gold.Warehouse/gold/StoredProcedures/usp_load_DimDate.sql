CREATE   PROCEDURE gold.usp_load_DimDate AS
BEGIN
    TRUNCATE TABLE gold.DimDate;
    INSERT INTO gold.DimDate
    SELECT date_key, [date], [year], [quarter], [month], month_name, year_month, [day],
           day_of_week, day_name, week_of_year, CAST(is_weekend AS bit)
    FROM lh_silver.dbo.calendar;
END;

GO