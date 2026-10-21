"""Sub-clusters (logic doc §4–5): groups of similar reels, found with HDBSCAN over cosine
distance between embeddings. A sub-cluster is always a group, never a single reel: reels
that fit no group are left out ("noise")."""

from __future__ import annotations

import statistics
from dataclasses import dataclass

import numpy as np
from sklearn.cluster import HDBSCAN

from curo.services.metrics import LIFT_METRICS, Lift

MIN_GROUP = 3


@dataclass
class Group:
    reel_ids: list[str]
    centroid: list[float]


def find_groups(vectors: dict[str, list[float]], min_size: int = MIN_GROUP) -> list[Group]:
    """Groups of at least ``min_size`` reels, largest first."""
    ids = sorted(vectors)
    if len(ids) < max(min_size, 2):
        return []
    x = np.asarray([vectors[i] for i in ids], dtype=float)
    x /= np.linalg.norm(x, axis=1, keepdims=True).clip(min=1e-12)
    distance = np.clip(1.0 - x @ x.T, 0.0, 2.0)
    labels = HDBSCAN(
        min_cluster_size=min_size,
        min_samples=2,
        metric="precomputed",
        allow_single_cluster=False,
        copy=True,
    ).fit_predict(distance)
    groups = []
    for label in sorted(set(labels) - {-1}):
        members = [ids[k] for k in range(len(ids)) if labels[k] == label]
        if len(members) < min_size:
            continue
        c = x[labels == label].mean(axis=0)
        c /= max(float(np.linalg.norm(c)), 1e-12)
        groups.append(Group(members, c.round(6).tolist()))
    return sorted(groups, key=lambda g: (-len(g.reel_ids), g.reel_ids[0]))


def nearest_to_centroid(group: Group, vectors: dict[str, list[float]], k: int = 8) -> list[str]:
    c = np.asarray(group.centroid)
    return sorted(group.reel_ids, key=lambda r: -float(np.dot(c, vectors[r])))[:k]


def group_lifts(reel_ids: list[str], lifts: dict[str, dict[str, Lift]]) -> dict[str, dict]:
    """Median lift per metric over the group's reels that have it (with n)."""
    out = {}
    for metric in LIFT_METRICS:
        values = [lifts[r][metric].lift for r in reel_ids if metric in lifts.get(r, {})]
        if values:
            out[metric] = {"lift": round(statistics.median(values), 3), "n": len(values)}
    return out


def match_previous(
    new: list[list[str]], old: dict[str, list[str]], min_jaccard: float = 0.5
) -> dict[int, str]:
    """Keep a sub-cluster's id when most of its reels are the same as before (Jaccard ≥ 0.5),
    so saved references survive a recompute. Returns new index → old id."""
    pairs = []
    for i, members in enumerate(new):
        a = set(members)
        for old_id, old_members in old.items():
            b = set(old_members)
            jac = len(a & b) / len(a | b) if a | b else 0.0
            if jac >= min_jaccard:
                pairs.append((jac, i, old_id))
    taken_new: set[int] = set()
    taken_old: set[str] = set()
    out: dict[int, str] = {}
    for _jac, i, old_id in sorted(pairs, reverse=True):
        if i not in taken_new and old_id not in taken_old:
            out[i] = old_id
            taken_new.add(i)
            taken_old.add(old_id)
    return out
