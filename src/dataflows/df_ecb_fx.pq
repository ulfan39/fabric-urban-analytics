// Dataflow Gen2: df_ecb_fx   ->  query name: ecb_fx
// Destination: lakehouse lh_bronze, table ecb_fx, update method: Replace
// OBS_VALUE = US dollars for 1 euro (ECB reference rate, TARGET working days only).
let
    ConfigUrl   = "https://raw.githubusercontent.com/ulfan39/fabric-urban-analytics/main/config/sources.json",
    Config      = Json.Document(Web.Contents(ConfigUrl)),
    SourceCfg   = List.First(List.Select(Config[sources], each [name] = "ecb_fx_usd_eur")),
    P           = SourceCfg[bronze][params],
    Raw         = Csv.Document(Web.Contents(P[base_url], [
                      RelativePath = "service/data/EXR/" & P[series_key],
                      Query        = [format = "csvdata", startPeriod = P[start_date]]]),
                      [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),
    Headers     = Table.PromoteHeaders(Raw, [PromoteAllScalars = true]),
    Selected    = Table.SelectColumns(Headers, {"TIME_PERIOD", "OBS_VALUE", "CURRENCY", "CURRENCY_DENOM"}),
    Renamed     = Table.RenameColumns(Selected, {
                      {"TIME_PERIOD", "time_period"}, {"OBS_VALUE", "obs_value"},
                      {"CURRENCY", "currency"}, {"CURRENCY_DENOM", "currency_denom"}}),
    Typed       = Table.TransformColumnTypes(Renamed, {
                      {"time_period", type text}, {"obs_value", type number},
                      {"currency", type text}, {"currency_denom", type text}}, "en-US"),
    Stamped     = Table.AddColumn(Typed, "ingested_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow()), type datetime)
in
    Stamped
