# %% [markdown]
# # nb_setup - one-time setup (run manually, never scheduled)
# 1. creates the folder structure in **lh_bronze** Files,
# 2. downloads the configuration from Git into the cache,
# 3. stores the OpenAQ API key in the restricted table **lh_bronze.cfg_secrets**
#    (secrets are never committed to Git; in production this would be Azure Key Vault).
#
# **After running: delete the key from the parameter cell before committing the notebook.**

# %% tags=["parameters"]
openaq_api_key = ""        # paste the key, run, then clear this value again

# %%
%run nb_common

# %%
lake = get_lake()
cfg = load_config(lake.files())
print("config:", [s["name"] + (" (enabled)" if s.get("enabled", True) else " (disabled)") for s in cfg["sources"]])
for folder in ["raw", "config"]:
    notebookutils.fs.mkdirs(lake.files(folder))

# %%
if openaq_api_key.strip():
    from pyspark.sql import Row
    (spark.createDataFrame([Row(name="openaq_api_key", value=openaq_api_key.strip())])
          .write.format("delta").mode("overwrite").save(lake.bronze_table("cfg_secrets")))
    print("cfg_secrets written - now clear the parameter value")
else:
    print("no key given - cfg_secrets unchanged")
