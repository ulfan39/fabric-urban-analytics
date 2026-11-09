# %% [markdown]
# # nb_silver_load
# Bronze -> Silver for every enabled source in the configuration:
# new bronze files (or the dataflow table) -> transform from `nb_transforms` -> Delta table -> `_load_log`.
# A failing source does not stop the others; the notebook fails at the end so the pipeline shows the error.

# %% tags=["parameters"]
sources = "all"            # comma separated source names or "all"
run_id = ""                # pipeline run id (passed by the pipeline), for the load log

# %%
%run nb_common

# %%
%run nb_transforms

# %%
import datetime as dt
import traceback
import uuid

lake = get_lake()
cfg = load_config(lake.files())
run_id = run_id or str(uuid.uuid4())
wanted = None if sources.strip() == "all" else {s.strip() for s in sources.split(",")}


def files_to_process(src):
    """New or re-downloaded bronze files of a file based source."""
    b = src["bronze"]
    extension = b["file_name"].rsplit(".", 1)[-1]
    found = [f for f in fs_ls_recursive(lake.files(landing_root(b["landing_folder"]))) if f[0].endswith("." + extension)]
    done = processed_files(spark, lake, src["name"])
    return [f for f in found if done.get(f[0]) != f[2]]          # new file or a newer copy


def run_source(src):
    started = utc_now()
    spec = src["silver"]
    file_based = src["bronze"]["method"] in ("pipeline_copy", "notebook_http")
    files = files_to_process(src) if file_based else None
    if file_based and not files:
        print(f"{src['name']}: nothing new")
        return []
    df, stats = TRANSFORMS[spec["transform"]](spark, lake, src, files)
    df = df.cache()
    rows_out = df.count()
    write_table(spark, lake, df, lake.silver_table(spec["table"]), spec)
    print(f"{src['name']}: {rows_out:,} rows -> {spec['table']} ({spec.get('write_mode', 'overwrite')})")

    # one log row per bronze file; rows_out per file is known only when the output keeps source_file
    out_per_file = ({r.source_file: r["count"] for r in df.groupBy("source_file").count().collect()}
                    if "source_file" in df.columns else {})
    modified = {path: mtime for path, _, mtime in (files or [])}
    return [{"run_id": run_id, "source": src["name"], "silver_table": spec["table"],
             "bronze_file": None if f == "*" else f, "bronze_modified": modified.get(f),
             "rows_in": s["rows_in"], "rows_rejected": s["rows_rejected"],
             "rows_out": out_per_file.get(f, rows_out if len(stats) == 1 else None),
             "status": "succeeded", "started_at": started, "finished_at": utc_now()}
            for f, s in stats.items()]


failures = []
for src in cfg["sources"]:
    if not src.get("enabled", True) or "silver" not in src or (wanted and src["name"] not in wanted):
        continue
    try:
        entries = run_source(src)
    except Exception as e:
        traceback.print_exc()
        failures.append(src["name"])
        entries = [{"run_id": run_id, "source": src["name"], "silver_table": src["silver"]["table"],
                    "status": "failed", "message": str(e)[:2000], "started_at": utc_now(), "finished_at": utc_now()}]
    if entries:
        log_load(spark, lake, entries)

# %%
# calendar = source of DimDate, from defaults.calendar_start to the end of next year
start = cfg["defaults"]["calendar_start"]
end = f"{dt.date.today().year + 1}-12-31"
write_table(spark, lake, build_calendar(spark, start, end), lake.silver_table("calendar"), {"write_mode": "overwrite"})
print(f"calendar {start} .. {end}")

# %%
if failures:
    raise RuntimeError(f"silver load failed for: {', '.join(failures)} (see _load_log)")
print("silver load finished")
