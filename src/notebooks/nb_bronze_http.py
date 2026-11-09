# %% [markdown]
# # nb_bronze_http
# Downloads the enabled `notebook_http` sources month by month into lh_bronze/Files, unchanged.
# The current and previous month are downloaded again on every run because they are still filling up.

# %% tags=["parameters"]
sources = "all"            # comma separated source names or "all"

# %%
%run nb_common

# %%
import datetime as dt
import time
import requests

lake = get_lake()
cfg = load_config(lake.files())
wanted = None if sources.strip() == "all" else {s.strip() for s in sources.split(",")}
today = dt.date.today()
refresh_from = (today.replace(day=1) - dt.timedelta(days=1)).replace(day=1)   # first day of previous month

downloaded = 0
for src in enabled_sources(cfg, "notebook_http"):
    if wanted and src["name"] not in wanted:
        continue
    b = src["bronze"]
    start = parse_date(b.get("start_date") or cfg["defaults"]["start_date"])
    for y, m in month_range(start, today):
        v = month_values(y, m)
        target = lake.files(f"{render(b['landing_folder'], **v)}/{render(b['file_name'], **v)}")
        if fs_exists(target) and dt.date(y, m, 1) < refresh_from:
            continue
        if v["month_end"] > today.isoformat():
            v["month_end"] = (today - dt.timedelta(days=1)).isoformat()      # archive APIs end yesterday
        query = {k: render(str(val), **v) for k, val in b.get("query", {}).items()}
        r = requests.get(b["url"], params=query, timeout=60)
        r.raise_for_status()
        fs_put(target, r.text)
        downloaded += 1
        print(f"{src['name']} {v['yyyy']}-{v['mm']} -> {target}")
        time.sleep(0.5)                                                     # be polite to free APIs
print(f"{downloaded} file(s) downloaded")
