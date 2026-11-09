// Dataflow Gen2: df_openaq   ->  query name: openaq_sensor_days
// Destination: lakehouse lh_bronze, table openaq_sensor_days, update method: Replace
// Needs the query "Secrets" (Get data > Lakehouse > lh_bronze > table cfg_secrets), see docs/01_setup.md.
// All parameters come from config/sources.json in Git (source "openaq_air_quality").
let
    ConfigUrl   = "https://raw.githubusercontent.com/ulfan39/fabric-urban-analytics/main/config/sources.json",
    Config      = Json.Document(Web.Contents(ConfigUrl)),
    SourceCfg   = List.First(List.Select(Config[sources], each [name] = "openaq_air_quality")),
    P           = SourceCfg[bronze][params],
    ApiKey      = Table.SelectRows(Secrets, each [name] = "openaq_api_key"){0}[value],
    DateFrom    = P[start_date],
    DateTo      = Date.ToText(Date.From(DateTimeZone.UtcNow()), "yyyy-MM-dd"),
    Limit       = Text.From(P[page_limit]),

    // one API call; 1 second pause because OpenAQ allows 60 requests per minute
    GetJson = (path as text, query as record) as record =>
        Function.InvokeAfter(
            () => Json.Document(Web.Contents(P[base_url], [
                    RelativePath = path,
                    Query        = query,
                    Headers      = [#"X-API-Key" = ApiKey, Accept = "application/json"]])),
            #duration(0, 0, 0, 1)),

    // all pages of an endpoint: page = 1, 2, ... until a page has fewer rows than the limit
    GetAll = (path as text, query as record) as list =>
        List.Combine(List.Generate(
            () => [page = 1, rows = GetJson(path, query & [limit = Limit, page = "1"])[results]],
            each List.Count([rows]) > 0,
            each [page = [page] + 1,
                  rows = if List.Count([rows]) < Number.From(Limit) then {}
                         else GetJson(path, query & [limit = Limit, page = Text.From([page] + 1)])[results]],
            each [rows])),

    // monitoring locations inside the NYC bounding box, one row per sensor
    Locations   = GetAll("v3/locations", [bbox = P[bbox]]),
    LocTable    = Table.FromRecords(List.Transform(Locations, each [
                      location_id   = [id],
                      location_name = [name],
                      latitude      = try [coordinates][latitude]  otherwise null,
                      longitude     = try [coordinates][longitude] otherwise null,
                      sensors       = [sensors]])),
    SensorRows  = Table.ExpandListColumn(LocTable, "sensors"),
    SensorInfo  = Table.AddColumn(SensorRows, "s", each [
                      sensor_id = [sensors][id],
                      parameter = [sensors][parameter][name],
                      units     = [sensors][parameter][units]]),
    Sensors     = Table.ExpandRecordColumn(Table.RemoveColumns(SensorInfo, {"sensors"}), "s", {"sensor_id", "parameter", "units"}),
    Wanted      = Table.SelectRows(Sensors, each List.Contains(P[parameters], [parameter])),

    // daily averages of every wanted sensor
    WithDays    = Table.AddColumn(Wanted, "days", each
                      GetAll("v3/sensors/" & Text.From([sensor_id]) & "/days", [date_from = DateFrom, date_to = DateTo])),
    DayRows     = Table.SelectRows(Table.ExpandListColumn(WithDays, "days"), each [days] <> null),
    DayInfo     = Table.AddColumn(DayRows, "d", each [
                      date         = Date.From(DateTime.FromText(Text.Start([days][period][datetimeFrom][local], 19))),
                      value        = [days][value],
                      min          = try [days][summary][min] otherwise null,
                      max          = try [days][summary][max] otherwise null,
                      coverage_pct = try [days][coverage][percentComplete] otherwise null]),
    Expanded    = Table.ExpandRecordColumn(Table.RemoveColumns(DayInfo, {"days"}), "d",
                      {"date", "value", "min", "max", "coverage_pct"}),
    Stamped     = Table.AddColumn(Expanded, "ingested_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow())),
    Typed       = Table.TransformColumnTypes(Stamped, {
                      {"location_id", Int64.Type}, {"location_name", type text}, {"latitude", type number},
                      {"longitude", type number}, {"sensor_id", Int64.Type}, {"parameter", type text},
                      {"units", type text}, {"date", type date}, {"value", type number}, {"min", type number},
                      {"max", type number}, {"coverage_pct", type number}, {"ingested_at", type datetime}})
in
    Typed
