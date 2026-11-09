# %% [markdown]
# # nb_bronze_plan_files
# First activity of pipeline `pl_bronze_files`. Lists the files of all enabled `pipeline_copy` sources that
# are published but not yet in lh_bronze, and returns them as JSON to the pipeline's ForEach + Copy activity.

# %% tags=["parameters"]
force_months = ""          # e.g. "2025-03,2025-04" to re-copy months that already exist

# %%
%run nb_common

# %%
import datetime as dt
import json
import requests

lake = get_lake()
cfg = load_config(lake.files())
forced = {m.strip() for m in force_months.split(",") if m.strip()}
today = dt.date.today()

items = []
for src in enabled_sources(cfg, "pipeline_copy"):
    b = src["bronze"]
    if b["frequency"] == "once":
        periods = [{}]
    else:
        start = parse_date(b.get("start_date") or cfg["defaults"]["start_date"])
        periods = [month_values(y, m) for y, m in month_range(start, today)]
    for v in periods:
        rel_url = render(b["relative_url"], **v)
        folder = render(b["landing_folder"], **v)
        name = render(b["file_name"], **v)
        ym = f"{v['yyyy']}-{v['mm']}" if v else ""
        if fs_exists(lake.files(f"{folder}/{name}")) and ym not in forced:
            continue
        url = f"{b['base_url'].rstrip('/')}/{rel_url}"
        try:
            ok = requests.head(url, timeout=20, allow_redirects=True).status_code == 200
        except Exception as e:
            print(f"HEAD failed for {url}: {e}")
            ok = False
        if not ok:
            print(f"not published yet: {url}")
            continue
        items.append({"source": src["name"], "relative_url": rel_url,
                      "target_folder": folder, "file_name": name})

print(f"{len(items)} file(s) to copy")
for it in items:
    print(" ", it["relative_url"], "->", it["target_folder"])

# %%
notebookutils.notebook.exit(json.dumps(items))
