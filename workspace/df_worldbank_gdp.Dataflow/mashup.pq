[StagingDefinition = [Kind = "FastCopy"]]
section Section1;
[DataDestinations = {[Definition = [Kind = "Reference", QueryName = "worldbank_gdp_DataDestination", IsNewTarget = true], Settings = [Kind = "Automatic", TypeSettings = [Kind = "Table"]]]}]
shared worldbank_gdp = let
    ConfigUrl   = "https://raw.githubusercontent.com/ulfan39/fabric-urban-analytics/main/config/sources.json",
    Config      = Json.Document(Web.Contents(ConfigUrl)),
    SourceCfg   = List.First(List.Select(Config[sources], each [name] = "worldbank_gdp")),
    P           = SourceCfg[bronze][params],
    Countries   = Text.Combine(P[countries], ";"),
    Years       = Text.From(P[from_year]) & ":" & Text.From(Date.Year(DateTime.LocalNow())),
    Response    = Json.Document(Web.Contents(P[base_url], [
                      RelativePath = "v2/country/" & Countries & "/indicator/" & P[indicator],
                      Query        = [format = "json", per_page = "20000", date = Years]])),
    Rows        = Response{1},
    AsTable     = Table.FromRecords(List.Transform(Rows, each [
                      country_code = [countryiso3code],
                      country_name = [country][value],
                      indicator    = [indicator][id],
                      year         = [date],
                      value        = [value]])),
    Stamped     = Table.AddColumn(AsTable, "ingested_at", each DateTimeZone.RemoveZone(DateTimeZone.UtcNow())),
    Typed       = Table.TransformColumnTypes(Stamped, {
                      {"country_code", type text}, {"country_name", type text}, {"indicator", type text},
                      {"year", type text}, {"value", type number}, {"ingested_at", type datetime}})
in
    Typed;
shared worldbank_gdp_DataDestination = let
  Pattern = Lakehouse.Contents([HierarchicalNavigation = true, EnableVorder = true, OutputMetadataRefresh = true, CreateNavigationProperties = false, EnableFolding = false]),
  Navigation_1 = Pattern{[workspaceId = "999d2239-9696-4a21-a6ff-10b7ee50a9c5"]}[Data],
  Navigation_2 = Navigation_1{[lakehouseId = "09cf8e10-e470-4b71-bf27-568e52aca825"]}[Data],
  Navigation_3 = Navigation_2{[Id = "dbo", ItemKind = "Schema"]}[Data],
  TableNavigation = Navigation_3{[Id = "worldbank_gdp", ItemKind = "Table"]}?[Data]?
in
  TableNavigation;
