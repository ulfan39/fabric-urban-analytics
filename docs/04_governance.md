# 4. Governance policies

## Source control and change management
* All workspace items are synced with GitHub (Fabric Git integration, folder `workspace/`); SQL, M and notebook
  sources are additionally kept in `src/`.
* Changes go through a branch and pull request; GitHub Actions runs the unit tests (`.github/workflows/tests.yml`).
* `config/sources.json` is the only place where sources are defined; pipelines and dataflows read it from `main`.

## Naming
| object | prefix | example |
|---|---|---|
| lakehouse / warehouse | `lh_` / `wh_` | `lh_bronze`, `wh_gold` |
| notebook / pipeline / dataflow | `nb_` / `pl_` / `df_` | `nb_silver_load`, `pl_master`, `df_openaq` |
| gold tables | `Dim*` / `Fact*` in schema `gold` | `gold.FactTaxiDaily` |
| load procedures | `gold.usp_load_<Table>` | `gold.usp_load_DimFX` |

## Access
| role | workspace role | can |
|---|---|---|
| Data engineer | Admin / Member | edit all items, commit to Git |
| Analyst | Viewer + Build on the semantic model | read gold, build reports |
| Report consumer | app / report access only | view reports; **RLS** role `Borough` filters `DimZone[Borough]` (optional) |

`lh_bronze.cfg_secrets` is not shared outside the engineering role. Secrets are never stored in Git;
in production they move to Azure Key Vault.

## Data classification
Sources are public open data. TLC trip records contain no personal data (no names, card numbers or exact
addresses; locations are zone ids). Classification: *Public*. Sensitivity label (if available): *General*.

## Data quality
* Rules per dataset are implemented in silver (see data dictionary) and counted per load in `_load_log`.
* Monitoring: `_load_log` (silver), `meta.LoadHistory` and `meta.vw_TableCounts` (gold); pipeline failure alerts.
* Additional automated checks with Great Expectations (integration task).

## Retention and history
* Bronze: raw files are kept (re-processing). Silver/Gold Delta tables keep 7 days of history
  (`VACUUM` default) for time travel and rollback.
* Taxi history window = `start_date` in the configuration.

## Lineage
Fabric lineage view (item level) and the diagram in [02_architecture.md](02_architecture.md); Purview (optional)
for column-level lineage. Every silver row carries `ingested_at` and, for taxi, `source_file`.

## Refresh schedule
`pl_master` daily at 06:00 (TLC publishes monthly, OpenAQ/ECB daily). The pipeline can be run manually at any time
(idempotent).
