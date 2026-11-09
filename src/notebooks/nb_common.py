# %% [markdown]
# # nb_common
# Shared helpers, loaded by the other notebooks with `%run nb_common`:
# configuration from Git, lakehouse paths, file helpers, month ranges, the Delta writer and the load log.

# %%
import datetime as dt
import json
import os
import re

import requests

CONFIG_URL = "https://raw.githubusercontent.com/ulfan39/fabric-urban-analytics/main/config/sources.json"
CONFIG_CACHE = "config/sources.json"      # inside lh_bronze/Files
LOAD_LOG = "_load_log"
BRONZE_LAKEHOUSE, SILVER_LAKEHOUSE = "lh_bronze", "lh_silver"

try:
    import notebookutils                  # exists only inside Fabric
    IS_FABRIC = True
except ImportError:
    notebookutils = None
    IS_FABRIC = False


# ------------------------------------------------------------------ lakehouse paths
class Lake:
    def __init__(self, bronze_root, silver_root, table_format="delta", bronze_schema="", silver_schema=""):
        self.bronze_root = bronze_root.rstrip("/")
        self.silver_root = silver_root.rstrip("/")
        self.table_format = table_format
        self.bronze_schema = bronze_schema
        self.silver_schema = silver_schema

    def files(self, rel=""):
        return f"{self.bronze_root}/Files/{rel}".rstrip("/")

    def bronze_table(self, name):
        return self._table(self.bronze_root, self.bronze_schema, name)

    def silver_table(self, name):
        return self._table(self.silver_root, self.silver_schema, name)

    @staticmethod
    def _table(root, schema, name):
        return f"{root}/Tables/{schema}/{name}" if schema else f"{root}/Tables/{name}"


def _lakehouse_root(name):
    try:
        return notebookutils.lakehouse.getWithProperties(name)["properties"]["abfsPath"]
    except Exception:
        ws = notebookutils.runtime.context["currentWorkspaceId"]
        return f"abfss://{ws}@onelake.dfs.fabric.microsoft.com/{notebookutils.lakehouse.get(name)['id']}"


def _schema_folder(root):
    # lakehouses created with "Lakehouse schemas" keep tables in Tables/dbo/
    return "dbo" if notebookutils.fs.exists(f"{root}/Tables/dbo") else ""


def get_lake():
    if IS_FABRIC:
        b = _lakehouse_root(BRONZE_LAKEHOUSE)
        s = _lakehouse_root(SILVER_LAKEHOUSE)
        return Lake(b, s, "delta", _schema_folder(b), _schema_folder(s))
    root = os.environ.get("LOCAL_LAKE_ROOT", os.path.abspath("_local_lake"))
    return Lake(f"{root}/bronze", f"{root}/silver", "parquet")


# ------------------------------------------------------------------ files (OneLake in Fabric, local disk in tests)
def fs_exists(path):
    return notebookutils.fs.exists(path) if IS_FABRIC else os.path.exists(path)


def fs_ls_recursive(path):
    """[(path, size, modify_time_ms)] of all files below path."""
    if not fs_exists(path):
        return []
    out = []
    if IS_FABRIC:
        stack = [path]
        while stack:
            for f in notebookutils.fs.ls(stack.pop()):
                if f.isDir:
                    stack.append(f.path)
                else:
                    out.append((f.path, f.size, f.modifyTime))
    else:
        for d, _, names in os.walk(path):
            for n in names:
                p = os.path.join(d, n)
                out.append((p, os.path.getsize(p), int(os.path.getmtime(p) * 1000)))
    return sorted(out)


def fs_put(path, text):
    if IS_FABRIC:
        notebookutils.fs.put(path, text, True)
    else:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def fs_read(path):
    if IS_FABRIC:
        return notebookutils.fs.head(path, 50 * 1024 * 1024)
    with open(path, encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------ configuration
def load_config(lake_files_root):
    """Reads config/sources.json from GitHub and caches it in lh_bronze;
    the cached copy is used if GitHub is not reachable."""
    cache = f"{lake_files_root}/{CONFIG_CACHE}"
    try:
        r = requests.get(CONFIG_URL, timeout=20)
        r.raise_for_status()
        cfg = r.json()
        fs_put(cache, json.dumps(cfg, indent=2))
        return cfg
    except Exception as e:
        if not fs_exists(cache):
            raise
        print(f"WARNING: config download failed ({e}), using the cached copy")
        return json.loads(fs_read(cache))


def enabled_sources(cfg, method=None):
    return [s for s in cfg["sources"]
            if s.get("enabled", True) and (method is None or s["bronze"]["method"] == method)]


# ------------------------------------------------------------------ dates and path templates
def parse_date(s):
    return dt.date.fromisoformat(s) if s else None


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def month_range(start, end):
    """[(year, month)] from the month of start to the month of end, inclusive."""
    y, m, out = start.year, start.month, []
    while (y, m) <= (end.year, end.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def month_values(y, m):
    """Values for path/URL templates: {yyyy} {mm} {month_start} {month_end}."""
    first = dt.date(y, m, 1)
    last = (dt.date(y + 1, 1, 1) if m == 12 else dt.date(y, m + 1, 1)) - dt.timedelta(days=1)
    return {"yyyy": f"{y:04d}", "mm": f"{m:02d}", "month_start": first.isoformat(), "month_end": last.isoformat()}


def render(template, **values):
    return re.sub(r"\{([a-z_]+)\}", lambda match: str(values[match.group(1)]), template)


def landing_root(template):
    """'raw/nyc_taxi/yellow/year={yyyy}/month={mm}' -> 'raw/nyc_taxi/yellow'"""
    return template.split("{")[0].rsplit("/", 1)[0] if "{" in template else template


# ------------------------------------------------------------------ tables
def table_exists(spark, lake, path):
    if lake.table_format != "delta":
        return fs_exists(path)
    from delta.tables import DeltaTable
    return DeltaTable.isDeltaTable(spark, path)


def read_table(spark, lake, path):
    return spark.read.format(lake.table_format).load(path)


def write_table(spark, lake, df, path, spec):
    """Writes a silver table according to spec['write_mode']:
       overwrite         - whole table (small reference data)
       replace_partition - only the partitions contained in df (monthly taxi files)
       merge             - upsert on spec['keys'] (late or corrected records)"""
    mode = spec.get("write_mode", "overwrite")
    parts = spec.get("partition_by", [])
    writer = df.write.format("delta")
    if mode == "overwrite" or not table_exists(spark, lake, path):
        writer = writer.mode("overwrite").option("overwriteSchema", "true")
        if parts:
            writer = writer.partitionBy(*parts)
        writer.save(path)
    elif mode == "replace_partition":
        values = ", ".join(f"'{r[0]}'" for r in df.select(parts[0]).distinct().collect())
        writer.mode("overwrite").option("replaceWhere", f"{parts[0]} IN ({values})").save(path)
    elif mode == "merge":
        from delta.tables import DeltaTable
        condition = " AND ".join(f"t.{k} = s.{k}" for k in spec["keys"])
        (DeltaTable.forPath(spark, path).alias("t").merge(df.alias("s"), condition)
            .whenMatchedUpdateAll().whenNotMatchedInsertAll().execute())
    else:
        raise ValueError(f"unknown write_mode '{mode}'")


# ------------------------------------------------------------------ load log
def processed_files(spark, lake, source_name):
    """{bronze file: modify time} of the files already loaded successfully."""
    path = lake.silver_table(LOAD_LOG)
    if not table_exists(spark, lake, path):
        return {}
    rows = (read_table(spark, lake, path)
            .where(f"source = '{source_name}' AND status = 'succeeded' AND bronze_file IS NOT NULL")
            .select("bronze_file", "bronze_modified").collect())
    return {r.bronze_file: r.bronze_modified for r in rows}


LOAD_LOG_SCHEMA = ("run_id string, source string, bronze_file string, bronze_modified long, silver_table string, "
                   "rows_in long, rows_out long, rows_rejected long, status string, message string, "
                   "started_at timestamp, finished_at timestamp")


def log_load(spark, lake, entries):
    columns = [c.split()[0] for c in LOAD_LOG_SCHEMA.split(", ")]
    df = spark.createDataFrame([tuple(e.get(c) for c in columns) for e in entries], LOAD_LOG_SCHEMA)
    df.write.format(lake.table_format).mode("append").save(lake.silver_table(LOAD_LOG))
