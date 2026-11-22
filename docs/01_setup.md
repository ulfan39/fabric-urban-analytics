# 1. Setup in Microsoft Fabric

Order matters: each step uses items created by the previous ones. Names are used by the code - keep them.

## 1.1 Workspace and items

1. Capacity. This project runs on a paid **F2** capacity created in Azure (Azure portal > Microsoft Fabric >
   Create; resource group `rg-fabric`, name `fabriculfan01`), because the Fabric trial is disabled in the
   university tenant. The region is **Poland Central**: the subscription policy only allows certain regions.
   Overage protection is off. **Pause the capacity in the Azure portal when it is not in use** - an F2 is billed
   per hour while it runs, and items cannot be opened while it is paused (Resume first).
   With a Fabric trial the steps below are the same.
2. Create a workspace on that capacity, e.g. `nyc-urban-analytics`.
3. Create two **Lakehouses**: `lh_bronze`, `lh_silver` (keep "Lakehouse schemas" as offered; both variants work).
4. Create a **Warehouse**: `wh_gold`.

## 1.2 Git integration (source control)

The workspace is connected to **Azure DevOps**; GitHub is a public mirror of the same repository.

* Azure DevOps is the Fabric Git provider because the tenant setting
  *Users can sync workspace items with GitHub repositories* is disabled (the GitHub option is greyed out).
* GitHub (`ulfan39/fabric-urban-analytics`, public) stays because the notebooks and dataflows read
  `config/sources.json` from `raw.githubusercontent.com` without authentication, and GitHub Actions runs the tests.

Steps:

1. GitHub: create the public repository `fabric-urban-analytics` and push this project to `main`.
2. Azure DevOps (`https://aex.dev.azure.com/me` if `dev.azure.com` redirects to the Azure portal): create the
   organization `ulfan-ibrahimov` and the project `fabric-urban-analytics`, then Repos > **Import repository** >
   the GitHub URL. Sign in with the same account as in Fabric.
3. Fabric: Workspace settings > **Git integration** > Azure DevOps > organization / project / repository >
   branch `main`, **Git folder `workspace`** > Connect and sync.
4. From now on: change items in Fabric, then **Source control > Commit**. Changes made in Git are applied with
   **Source control > Update**.
5. Keep both remotes equal from a local clone (Azure DevOps: Repos > Clone > *Generate Git Credentials*):

   ```bash
   git remote add ado https://dev.azure.com/ulfan-ibrahimov/_git/fabric-urban-analytics
   git pull origin main          # GitHub (e.g. edits of config/sources.json)
   git fetch ado && git merge ado/main   # Fabric commits
   git push origin main && git push ado main
   ```

> If the GitHub option is enabled in a tenant, the workspace can be connected to GitHub directly
> (fine-grained token with *Contents: Read and write*) and step 5 is not needed.

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
   right-click > uncheck *Enable staging*. Then Options > Privacy > **Ignore the Privacy levels**
   (the key comes from the lakehouse and is sent to the API, a different source; without this the
   dataflow refuses to combine them).
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

> In this deployment yellow taxi uses `"start_date": "2026-06-01"` (set in `config/sources.json`) to keep the
> data volume and the F2 compute cost small: about 14.6 million trips. To load more history, change only this
> date and run `pl_master`; the planner copies the missing months and silver processes only the new files.

## 1.7 Warehouse objects

Open `wh_gold` > New SQL query, run `src/warehouse/01_tables.sql`, then `02_procedures.sql`, then `03_views.sql`.
The Fabric SQL editor accepts `GO` (each `GO` starts a new batch).

> Fabric Warehouse does not support queries that reference variables inside table queries in distributed mode
> (error *Msg 16546*). Therefore `gold.usp_load_all` does not loop over `meta.GoldLoads` with variables; it
> builds one script from the table (`STRING_AGG`, one logged `TRY/CATCH` block per procedure) and runs it with
> `EXEC`. Test it with `EXEC gold.usp_load_all @RunId = 'manual-1';`.

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

The **Invoke pipeline** activity needs a connection of type *Fabric Data Pipelines*
(`conn_fabric_pipelines`, Organizational account, privacy level Organizational); create it from the activity's
Settings tab.

Schedule: Run > Schedule > daily 06:00, time zone Warsaw, end date 31/12/2026 (Phase 5 "automate refresh";
the default "every 15 minutes" would use the capacity all day). Commit the pipelines to Git.
A run where no new month is published only checks the sources and finishes quickly (bronze about 1.5 min),
because every step is incremental.

## 1.9 Check

```sql
-- wh_gold
SELECT * FROM meta.vw_TableCounts;
SELECT TOP 20 * FROM meta.LoadHistory ORDER BY StartedAt DESC;
-- lh_silver SQL endpoint
SELECT source, status, SUM(rows_in) rows_in, SUM(rows_rejected) rejected, MAX(finished_at) last_load
FROM dbo._load_log GROUP BY source, status;
```

## 1.10 Result of the first full load (this deployment)

Silver (`_load_log`):

| source | rows in | rejected | rows out | note |
|---|---|---|---|---|
| yellow taxi | 14,580,117 | 244,980 (1.7 %) | 14,277,018 | 58,119 duplicates removed |
| OpenAQ | 22,657 | 12 | 22,645 | |
| ECB FX | 1,759 | 0 | 2,509 | forward-filled to every calendar day |
| World Bank GDP | 156 | 0 | 156 | 6 countries from 2000 |
| taxi zones | 265 | 0 | 265 | |

Gold (`meta.vw_TableCounts`): DimDate 10,227 · DimZone 265 · DimAQLocation 55 · DimFX 2,509 · DimGDP 156 ·
FactTaxiDaily 29,242 · FactTaxiHourly 19,009 · FactAirQualityDaily 22,645. All eight procedures logged
`succeeded` in `meta.LoadHistory`.
