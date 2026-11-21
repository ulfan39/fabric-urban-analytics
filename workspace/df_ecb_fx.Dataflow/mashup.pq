[StagingDefinition = [Kind = "FastCopy"]]
section Section1;
[DataDestinations = {[Definition = [Kind = "Reference", QueryName = "ecb_fx_DataDestination", IsNewTarget = true], Settings = [Kind = "Automatic", TypeSettings = [Kind = "Table"]]]}]
shared ecb_fx = let
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
    Stamped;
shared ecb_fx_DataDestination = let
  Pattern = Lakehouse.Contents([HierarchicalNavigation = true, EnableVorder = true, OutputMetadataRefresh = true, CreateNavigationProperties = false, EnableFolding = false]),
  Navigation_1 = Pattern{[workspaceId = "999d2239-9696-4a21-a6ff-10b7ee50a9c5"]}[Data],
  Navigation_2 = Navigation_1{[lakehouseId = "09cf8e10-e470-4b71-bf27-568e52aca825"]}[Data],
  Navigation_3 = Navigation_2{[Id = "dbo", ItemKind = "Schema"]}[Data],
  TableNavigation = Navigation_3{[Id = "ecb_fx", ItemKind = "Table"]}?[Data]?
in
  TableNavigation;
