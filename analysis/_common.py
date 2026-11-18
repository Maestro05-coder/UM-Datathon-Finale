"""Shared helpers for every group script. One place for paths and small utilities."""
import os
import numpy as np
import pandas as pd
import duckdb

ANALYSIS = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ANALYSIS, "cache_full")          # light columns, from build_cache.py
PARTY_CACHE = os.path.join(ANALYSIS, "cache_party")   # account/party columns, from build_cache_party.py
CHARTS = os.path.join(ANALYSIS, "charts")


def ddb():
    """One DuckDB connection. Query the full 10M rows with SQL, nothing is held in RAM."""
    return duckdb.connect()


def full_glob(cache_dir=CACHE):
    """Glob string covering every part file, for read_parquet()."""
    return os.path.join(cache_dir, "part_*.parquet").replace("\\", "/")


def rand_sample(con, sql, pct=5):
    """Random sample of a query's result (bernoulli, not a stride - no aliasing risk).
    Use for plotting only; never quote a number from here as a fact."""
    return con.execute(f"SELECT * FROM ({sql}) USING SAMPLE {pct} PERCENT (bernoulli, 7)").df()

CORE_COLS = ["EPOCH_SECONDS", "CURRENCY_CODE", "USD_AMOUNT", "ORDERING_BIC8", "BENEFICIARY_BIC8",
             "BIC8_PATH", "TOTAL_DURATION", "CONTINUITY_QFLAG", "CURRENCY_CONVERSION_COUNT",
             "PARTICIPANT_COUNT", "TRANSACTION_TYPE_CODE", "ORDERING_TYPE", "BENEFICIARY_TYPE",
             "ANOMALY_TYPE", "half"]


def parts():
    return sorted(os.path.join(CACHE, f) for f in os.listdir(CACHE) if f.startswith("part_"))


def banks_of(path):
    """Split a route into the banks we can see, and count the '...' placeholders."""
    if not isinstance(path, str) or not path:
        return [], 0
    bits = path.split(";")
    return [b for b in bits if b != "..."], sum(1 for b in bits if b == "...")


def country_of(bic):
    """Characters 5-6 of a BIC8 are the country."""
    return bic[4:6] if isinstance(bic, str) and len(bic) >= 6 else ""


def med(x):
    x = np.asarray(x, dtype=float)
    return float(np.median(x)) if len(x) else float("nan")


def q(x, p):
    x = np.asarray(x, dtype=float)
    return float(np.percentile(x, p)) if len(x) else float("nan")


class Res:
    """Keeps a random sample of values so medians work without holding all 10m rows."""
    def __init__(self, cap=20_000, seed=0):
        self.data, self.n, self.cap = [], 0, cap
        self.rng = np.random.default_rng(seed)

    def add(self, v):
        self.n += 1
        if len(self.data) < self.cap:
            self.data.append(v)
        else:
            i = self.rng.integers(self.n)
            if i < self.cap:
                self.data[i] = v

    def med(self):
        return med(self.data)


def savefig(fig, name, group=None, dpi=150):
    """Save into the group's folder when given, else the shared charts/ dir."""
    out = os.path.join(ANALYSIS, "groups", group) if group else CHARTS
    os.makedirs(out, exist_ok=True)
    fig.tight_layout()
    # bbox_inches="tight" keeps titles/legends placed outside the axes from being clipped.
    fig.savefig(os.path.join(out, name), dpi=dpi, bbox_inches="tight", pad_inches=0.25)
    import matplotlib.pyplot as plt
    plt.close(fig)
    print("saved chart:", os.path.join("groups", group, name) if group else name)
