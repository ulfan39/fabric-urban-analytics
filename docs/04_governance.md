# 4. Governance policies

## Source control and change management
* All workspace items (notebooks, dataflows, pipelines, warehouse, semantic model, report) are synced with
  **Azure DevOps** through Fabric Git integration, folder `workspace/`. The same repository is mirrored to GitHub
  (see [01_setup.md](01_setup.md) 1.2). SQL, M and notebook sources are additionally kept in `src/`.
* The warehouse is versioned as a SQL project (tables, procedures, views as `.sql`); lakehouses are versioned as
  item definitions only - data is not stored in Git.
* GitHub Actions runs the unit tests on every push (`.github/workflows/tests.yml`).
* This is a one-person project, so commits go to `main`. In a team, changes would go through a feature branch
  and a pull request with the tests as a required check, and a separate test workspace connected to that branch.
* `config/sources.json` is the only place where sources are defined; notebooks and dataflows read it from `main`
  at run time, so a configuration change is a commit and is visible in the history.

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
* The OpenAQ key is written once by `nb_setup` and then removed from the notebook's parameter cell before the
  notebook is committed.
* Connections (`conn_tlc_cloudfront`, `conn_fabric_pipelines`, dataflow connections) live in Fabric's
  connection store and are not part of the Git definitions.

## Cost control
The F2 capacity is billed per running hour. It is paused in the Azure portal when no work is done, the schedule
runs once a day, and the taxi history window is kept small (`start_date`).

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
`pl_master` daily at 06:00 Warsaw time (TLC publishes monthly, OpenAQ/ECB daily). The pipeline can be run manually at any time
(idempotent).
