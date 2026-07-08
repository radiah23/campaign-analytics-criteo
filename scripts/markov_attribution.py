"""
Markov Chain Multi-Touch Attribution for the Criteo dataset.

Reconstructs per-user conversion paths, builds a first-order Markov
transition graph (Start -> touchpoints -> Conversion/Null), and computes
each channel's "removal effect" — the drop in total conversion
probability when that channel is removed from the graph.

NOTE: adjust USER_COL and CHANNEL_COL below to match your actual
schema (run a `SELECT * LIMIT 5` first to confirm column names).

Usage:
    python scripts/markov_attribution.py
"""
import sqlite3
from collections import defaultdict
from itertools import combinations

import numpy as np
import pandas as pd

DB_PATH = "data/criteo.db"
TABLE_NAME = "impressions"

# --- Adjust these to match your actual columns ---
USER_COL = "uid"              # groups impressions into a single path
CHANNEL_COL = "campaign"      # the touchpoint / channel identifier
TIME_COL = "timestamp"        # orders impressions within a path
CONVERSION_COL = "conversion" # 1 if this path ended in a conversion
# ---------------------------------------------------

START = "(start)"
CONVERSION = "(conversion)"
NULL = "(null)"


def load_paths(conn) -> pd.DataFrame:
    query = f"""
        SELECT {USER_COL}, {CHANNEL_COL}, {TIME_COL}, {CONVERSION_COL}
        FROM {TABLE_NAME}
    """
    df = pd.read_sql(query, conn)
    df = df.sort_values([USER_COL, TIME_COL])
    return df


def build_paths(df: pd.DataFrame) -> list[list[str]]:
    """Turn raw impressions into ordered channel sequences per user,
    each ending in (conversion) or (null)."""
    paths = []
    for uid, group in df.groupby(USER_COL):
        channels = [str(c) for c in group[CHANNEL_COL].tolist()]
        converted = group[CONVERSION_COL].max() == 1
        end_state = CONVERSION if converted else NULL
        paths.append([START] + channels + [end_state])
    return paths


def transition_counts(paths: list[list[str]]) -> dict:
    counts = defaultdict(lambda: defaultdict(int))
    for path in paths:
        for a, b in zip(path[:-1], path[1:]):
            counts[a][b] += 1
    return counts


def to_probabilities(counts: dict) -> dict:
    probs = {}
    for state, next_counts in counts.items():
        total = sum(next_counts.values())
        probs[state] = {k: v / total for k, v in next_counts.items()}
    return probs


def build_edges(probs: dict, states: list[str]) -> list[tuple[str, str, float]]:
    """Flatten the transition graph into (src, dst, prob) edges."""
    return [(s, nxt, p) for s in states for nxt, p in probs.get(s, {}).items()]


def conversion_probability(
    edges: list[tuple[str, str, float]],
    states: list[str],
    removed: set[str] | None = None,
) -> float:
    """Probability of eventually being absorbed into (conversion) from
    (start), optionally with certain channels removed (their traffic
    redirected to null).

    The aggregated transition graph is a general (possibly cyclic) Markov
    chain, not a DAG, so this solves the absorbing-chain linear system
    (I - Q)x = R instead of recursing — recursion would loop forever on
    cycles like campaign A -> B -> A.
    """
    removed = removed or set()
    transient = [s for s in states if s not in removed]
    idx = {s: i for i, s in enumerate(transient)}
    n = len(transient)
    Q = np.zeros((n, n))
    R = np.zeros(n)
    for s, nxt, p in edges:
        i = idx.get(s)
        if i is None:
            continue
        if nxt in removed or nxt == NULL:
            continue
        elif nxt == CONVERSION:
            R[i] += p
        else:
            j = idx.get(nxt)
            if j is not None:
                Q[i, j] += p
    x = np.linalg.solve(np.eye(n) - Q, R)
    return x[idx[START]]


def removal_effects(probs: dict, channels: list[str]) -> pd.DataFrame:
    states = [START] + channels
    edges = build_edges(probs, states)
    baseline = conversion_probability(edges, states)
    rows = []
    for ch in channels:
        p_without = conversion_probability(edges, states, removed={ch})
        effect = (baseline - p_without) / baseline if baseline > 0 else 0
        rows.append({"channel": ch, "removal_effect": effect})
    result = pd.DataFrame(rows).sort_values("removal_effect", ascending=False)
    result["attribution_share"] = result["removal_effect"] / result["removal_effect"].sum()
    return result.reset_index(drop=True)


def last_touch_baseline(paths: list[list[str]]) -> pd.DataFrame:
    """Simple last-touch credit, for comparison."""
    credit = defaultdict(int)
    for path in paths:
        if path[-1] == CONVERSION and len(path) >= 3:
            last_channel = path[-2]
            credit[last_channel] += 1
    total = sum(credit.values())
    rows = [{"channel": k, "last_touch_share": v / total} for k, v in credit.items()]
    return pd.DataFrame(rows).sort_values("last_touch_share", ascending=False).reset_index(drop=True)


def main():
    with sqlite3.connect(DB_PATH) as conn:
        df = load_paths(conn)

    print(f"Loaded {len(df):,} impressions across {df[USER_COL].nunique():,} users")

    paths = build_paths(df)
    n_converted = sum(1 for p in paths if p[-1] == CONVERSION)
    print(f"Built {len(paths):,} paths ({n_converted:,} converted)")

    counts = transition_counts(paths)
    probs = to_probabilities(counts)

    channels = sorted({c for path in paths for c in path if c not in (START, CONVERSION, NULL)})
    print(f"Found {len(channels)} distinct channels/campaigns")

    print("\nComputing Markov removal effects (this can take a while for many channels)...")
    markov_result = removal_effects(probs, channels)
    print("\n=== Markov Attribution (removal effect) ===")
    print(markov_result.to_string(index=False))

    lt_result = last_touch_baseline(paths)
    print("\n=== Last-Touch Baseline (for comparison) ===")
    print(lt_result.to_string(index=False))

    markov_result.to_csv("data/markov_attribution.csv", index=False)
    lt_result.to_csv("data/last_touch_baseline.csv", index=False)
    print("\nSaved results to data/markov_attribution.csv and data/last_touch_baseline.csv")


if __name__ == "__main__":
    main()
