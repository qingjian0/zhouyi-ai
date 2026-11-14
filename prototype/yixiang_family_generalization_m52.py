"""M52 family-level split auditing and paired cross-family evaluation.

This module prevents episode-level leakage from masquerading as
out-of-family generalization. Families, templates, generator lineages and
seed groups are atomic split units. Evaluation is macro-averaged by family.
"""
from dataclasses import dataclass
import random

VALID_SPLITS = {"train", "validation", "test"}


@dataclass(frozen=True)
class FamilySplitRecord:
    episode_id: str
    split: str
    family_id: str
    template_id: str
    mechanism_signature: str
    generator_lineage_id: str
    seed_group_id: str


@dataclass(frozen=True)
class SplitAudit:
    valid: bool
    errors: tuple
    counts_by_split: tuple
    groups_by_split: tuple


@dataclass(frozen=True)
class PairedFamilyEffect:
    baseline_a: str
    baseline_b: str
    family_count: int
    mean_difference: float
    lower: float
    upper: float
    confidence_level: float
    bootstrap_samples: int


def audit_family_split(records, require_all_splits=True):
    """Audit disjointness at episode, family, template, lineage and seed levels."""
    records = tuple(records)
    errors = []
    seen_episodes = set()
    group_splits = {name: {} for name in (
        "family_id", "template_id", "generator_lineage_id", "seed_group_id"
    )}
    counts = {split: 0 for split in sorted(VALID_SPLITS)}
    for record in records:
        if not isinstance(record, FamilySplitRecord):
            errors.append("invalid_record_type")
            continue
        if record.split not in VALID_SPLITS:
            errors.append("invalid_split:" + str(record.episode_id))
            continue
        counts[record.split] += 1
        if not record.episode_id or record.episode_id in seen_episodes:
            errors.append("duplicate_or_empty_episode_id:" + str(record.episode_id))
        seen_episodes.add(record.episode_id)
        for field, mapping in group_splits.items():
            value = getattr(record, field)
            if not value:
                errors.append("empty_" + field + ":" + str(record.episode_id))
                continue
            prior = mapping.get(value)
            if prior is not None and prior != record.split:
                errors.append("cross_split_leakage:" + field + ":" + value + ":"
                              + prior + "->" + record.split)
            else:
                mapping[value] = record.split
    if require_all_splits:
        for split, count in counts.items():
            if count == 0:
                errors.append("missing_split:" + split)
    return SplitAudit(
        not errors, tuple(sorted(set(errors))), tuple(sorted(counts.items())),
        tuple((field, tuple(sorted(mapping.items())))
              for field, mapping in sorted(group_splits.items())),
    )


def family_macro_average(scores_by_family):
    """Return an equal-weight family mean; reject empty or non-finite inputs."""
    if not scores_by_family:
        raise ValueError("empty_family_scores")
    values = []
    for family_id, score in sorted(scores_by_family.items()):
        if not family_id or isinstance(score, bool) or not isinstance(score, (int, float)):
            raise ValueError("invalid_family_score")
        if score != score or score in (float("inf"), float("-inf")):
            raise ValueError("non_finite_family_score")
        values.append(float(score))
    return sum(values) / len(values)


def paired_family_bootstrap(scores_a, scores_b, baseline_a="A", baseline_b="B",
                            samples=2000, seed=17, confidence_level=0.95):
    """Cluster bootstrap paired differences, resampling whole families."""
    if set(scores_a) != set(scores_b):
        raise ValueError("paired_family_sets_must_match")
    if not scores_a:
        raise ValueError("empty_family_scores")
    if not isinstance(samples, int) or isinstance(samples, bool) or samples < 100:
        raise ValueError("bootstrap_samples_must_be_at_least_100")
    if isinstance(confidence_level, bool) or not isinstance(confidence_level, (int, float)) or not 0.0 < confidence_level < 1.0:
        raise ValueError("invalid_confidence_level")
    families = tuple(sorted(scores_a))
    differences = []
    for family in families:
        a, b = scores_a[family], scores_b[family]
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or
               x in (float("inf"), float("-inf")) for x in (a, b)):
            raise ValueError("non_finite_paired_score:" + family)
        differences.append(float(a) - float(b))
    observed = sum(differences) / len(differences)
    rng = random.Random(seed)
    draws = []
    for _ in range(samples):
        selected = [differences[rng.randrange(len(differences))]
                    for _ in range(len(differences))]
        draws.append(sum(selected) / len(selected))
    draws.sort()
    alpha = (1.0 - confidence_level) / 2.0
    lower_index = max(0, min(samples - 1, int(alpha * samples)))
    upper_index = max(0, min(samples - 1, int((1.0 - alpha) * samples) - 1))
    return PairedFamilyEffect(
        baseline_a, baseline_b, len(families), observed,
        draws[lower_index], draws[upper_index], confidence_level, samples,
    )


def audit_comparison_protocol(train_records, validation_records, test_records):
    """Validate caller-declared partitions, then audit global split disjointness."""
    partitions = (
        ("train", tuple(train_records)),
        ("validation", tuple(validation_records)),
        ("test", tuple(test_records)),
    )
    records = []
    errors = []
    for expected_split, partition_records in partitions:
        for record in partition_records:
            if not isinstance(record, FamilySplitRecord):
                errors.append("invalid_record_type:" + expected_split)
                continue
            if record.split != expected_split:
                errors.append(
                    "partition_split_mismatch:" + expected_split + ":"
                    + str(record.split) + ":" + str(record.episode_id)
                )
            records.append(record)

    audit = audit_family_split(records, require_all_splits=True)
    if not errors:
        return audit
    return SplitAudit(
        False,
        tuple(sorted(set(audit.errors + tuple(errors)))),
        audit.counts_by_split,
        audit.groups_by_split,
    )
