// Dataflow Gen2: df_worldbank_gdp   ->  query name: worldbank_gdp
// Destination: lakehouse lh_bronze, table worldbank_gdp, update method: Replace
// Parameters (indicator, countries, from_year) come from config/sources.json (source "worldbank_gdp").
let
    ConfigUrl   = "https://raw.githubusercontent.com/ulfan39/fabric-urban-analytics/main/config/sources.json",
    Config      = Json.Document(Web.Contents(ConfigUrl)),
    SourceCfg   = List.First(List.Select(Config[sources], each [name] = "worldbank_gdp")),
    P           = SourceCfg[bronze][params],
    Countries   = Text.Combine(P[countries], ";"),
    Years       = Text.From(P[from_year]) & ":" & Text.From(Date.Year(DateTime.LocalNow())),

    // response = { meta-record, list-of-observations }; per_page large enough for one page
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
    Typed
