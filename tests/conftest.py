"""Local test harness: runs the Fabric notebooks' code on a local Spark session.

Notebook sources live in src/notebooks/*.py (percent format). Fabric magics (`%run ...`) and
`notebookutils` calls are stripped/stubbed; everything else is executed unchanged."""
import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NB = ROOT / "src" / "notebooks"


def notebook_code(name):
    src = (NB / f"{name}.py").read_text(encoding="utf-8")
    lines = []
    for line in src.splitlines():
        if line.startswith("%run") or line.startswith("notebookutils.notebook.exit"):
            continue
        lines.append(line)
    return "\n".join(lines)


def run_notebook(name, ns):
    exec(compile(notebook_code(name), f"{name}.py", "exec"), ns)
    if name == "nb_common":
        ns["write_table"] = parquet_write_table        # Delta jars are not available locally
    return ns


def parquet_write_table(spark, lake, df, path, spec):
    """Same three write modes as nb_common.write_table, implemented with plain parquet."""
    mode = spec.get("write_mode", "overwrite")
    parts = spec.get("partition_by", [])
    exists = os.path.exists(path)
    if mode == "overwrite" or not exists:
        w = df.write.mode("overwrite")
        (w.partitionBy(*parts) if parts else w).parquet(path)
    elif mode == "replace_partition":
        spark.conf.set("spark.sql.sources.partitionOverwriteMode", "dynamic")
        df.write.mode("overwrite").partitionBy(*parts).parquet(path)
    elif mode == "merge":
        keys = spec["keys"]
        old = spark.read.parquet(path)
        merged = (old.join(df.select(*keys).distinct(), keys, "left_anti").unionByName(df)
                     .select(*df.columns).localCheckpoint())        # cut lineage before overwriting the source
        merged.write.mode("overwrite").parquet(path)
    else:
        raise ValueError(mode)


@pytest.fixture(scope="session")
def spark():
    from pyspark.sql import SparkSession
    s = (SparkSession.builder.master("local[2]").appName("tests")
         .config("spark.ui.enabled", "false").config("spark.sql.shuffle.partitions", "4")
         .config("spark.sql.session.timeZone", "UTC").getOrCreate())
    s.sparkContext.setLogLevel("ERROR")
    yield s
    s.stop()


@pytest.fixture(scope="session")
def config():
    return json.loads((ROOT / "config" / "sources.json").read_text(encoding="utf-8"))
