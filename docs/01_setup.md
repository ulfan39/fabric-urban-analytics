# 1. Setup in Microsoft Fabric

Order matters: each step uses items created by the previous ones. Names are used by the code - keep them.

## 1.1 Workspace and items

1. Create a workspace (Fabric or Trial capacity), e.g. `nyc-urban-analytics`.
2. Create two **Lakehouses**: `lh_bronze`, `lh_silver` (keep "Lakehouse schemas" as offered; both variants work).
3. Create a **Warehouse**: `wh_gold`.

## 1.2 Git integration (source control)

1. GitHub: create the repository `fabric-urban-analytics` (public, so pipelines can read `config/sources.json`
   via `raw.githubusercontent.com`) and push this project to `main`.
2. GitHub > Settings > Developer settings > Fine-grained token: repository access = this repo,
   permission *Contents: Read and write*.
3. Fabric: Workspace settings > **Git integration** > GitHub > add account (token + repo URL) >
   branch `main`, **Git folder `workspace`** > Connect and sync.
4. From now on: change items in Fabric, then **Source control > Commit**. Changes made in Git
   (e.g. by a pull request) are applied with **Source control > Update**.

> If the tenant blocks GitHub sync, an admin has to enable *Users can sync workspace items with GitHub repositories*.

## 1.3 Notebooks

1. `python tools/build_notebooks.py` creates `dist/notebooks/*.ipynb`.
2. Workspace > Import > Notebook > From this computer > select all six files.
3. Open `nb_setup`, attach lakehouse `lh_bronze` (only needed for this notebook), paste the OpenAQ API key
   (free, https://explore.openaq.org/register) into the parameter cell, **Run all**, then delete the key from the cell.
   This creates `lh_bronze.cfg_secrets` and the `Files/raw`, `Files/config` folders.

The other notebooks resolve lakehouse paths by name (`nb_common.get_lake`), they need no default lakehouse.

## 1.4 Dataflows Gen2 (API sources → bronze tables)

For each of `df_openaq`, `df_worldbank_gdp`, `df_ecb_fx`:

1. New > **Dataflow Gen2** (keep *Enable Git integration, deployment pipelines and Public API scenarios* checked) > name as above.
2. Get data > **Blank query** > Advanced editor > paste the file from `src/dataflows/` > OK.
   Rename the query to the table name in the file header (`openaq_sensor_days`, `worldbank_gdp`, `ecb_fx`).
3. Connections: *Anonymous* for the web sources (raw.githubusercontent.com and the API host).
4. Only `df_openaq`: Get data > Lakehouse > `lh_bronze` > table `cfg_secrets`, rename the query to **`Secrets`**,
   right-click > uncheck *Enable staging*. Then Options > Privacy > **Allow combining data from multiple sources**
   (the API key and the API are different sources).
5. Data destination (bottom right of the main query) > Lakehouse > `lh_bronze` > new table with the same name >
   update method **Replace** > Save settings.
6. **Save & run** (Publish). Check the table in `lh_bronze`.

## 1.5 HTTP connection for the taxi files

Manage connections and gateways > New > Cloud > type **HTTP** > name `conn_tlc_cloudfront`,
URL `https://d37ci6vzurychx.cloudfront.net/`, authentication Anonymous.

## 1.6 Pipeline `pl_bronze_files` (file sources → bronze Files)

| # | activity | settings |
|---|---|---|
| 1 | **Notebook** `Plan files` | notebook `nb_bronze_plan_files` |
| 2 | **ForEach** `Copy each file` (on success of 1) | Items: `@json(activity('Plan files').output.result.exitValue)`, Sequential off, Batch count 4 |
| 2a | inside: **Copy data** `Copy file` | Source: connection `conn_tlc_cloudfront`, Relative URL `@item().relative_url`, file format **Binary**. Destination: Lakehouse `lh_bronze`, root folder **Files**, folder path `@item().target_folder`, file name `@item().file_name`, format **Binary** |
| 3 | **Notebook** `Generic HTTP sources` (on success of 1) | notebook `nb_bronze_http` (downloads sources with `method = notebook_http`) |

Run it once. The first run copies all months from `start_date` (about 60 MB per month).

## 1.7 Warehouse objects

Open `wh_gold` > New SQL query, run `src/warehouse/01_tables.sql`, then `02_procedures.sql`, then `03_views.sql`.
If the editor complains about `GO`, select one block (one `CREATE ...` statement) at a time and press Run.

## 1.8 Master pipeline `pl_master` (orchestration)

| # | activity | depends on | settings |
|---|---|---|---|
| 1 | **Invoke pipeline** `Bronze files` | - | pipeline `pl_bronze_files`, wait on completion |
| 2 | **Dataflow** `OpenAQ` | - | `df_openaq` |
| 3 | **Dataflow** `World Bank` | - | `df_worldbank_gdp` |
| 4 | **Dataflow** `ECB FX` | - | `df_ecb_fx` |
| 5 | **Notebook** `Silver` | 1-4 succeeded | `nb_silver_load`, base parameter `run_id` (String) = `@pipeline().RunId` |
| 6 | **Wait** `SQL endpoint sync` | 5 | 60 s (lets the lakehouse SQL endpoint see the new Delta versions) |
| 7 | **Stored procedure** `Gold` | 6 | warehouse `wh_gold`, procedure `gold.usp_load_all`, parameter `RunId` = `@pipeline().RunId` |
| 8 | **Semantic model refresh** (optional) | 7 | model `sm_nyc_urban` |

Schedule: Run > Schedule > daily 06:00 (Phase 5 "automate refresh"). Commit the pipelines to Git.

## 1.9 Check

```sql
-- wh_gold
SELECT * FROM meta.vw_TableCounts;
SELECT TOP 20 * FROM meta.LoadHistory ORDER BY StartedAt DESC;
-- lh_silver SQL endpoint
SELECT source, status, SUM(rows_in) rows_in, SUM(rows_rejected) rejected, MAX(finished_at) last_load
FROM dbo._load_log GROUP BY source, status;
```
