"""M50 end-to-end causal experiment runner wiring M44-M49 research primitives."""
from dataclasses import asdict
from hashlib import sha256
import json

from prototype.yixiang_scm_benchmark_m46 import SCMEnvironment, SCMSpec, SCMNode
from prototype.yixiang_evidence_event_ledger_m45 import EvidenceLedger
from prototype.yixiang_benchmark_baselines_m47 import (
    BaselineOutput, evaluate_episode, random_intervention_baseline,
    correlation_screen_baseline, oracle_diagnostic_baseline,
)
from prototype.yixiang_ablation_evaluation_m48 import (
    EpisodeRun, MetricSpec, compare_ablation,
)
from prototype.yixiang_reproducibility_manifest_m49 import (
    ArtifactRef, RunManifest, SplitItem, audit_manifest,
)
from prototype.yixiang_adaptive_policy_search_m40 import PolicyNode, SearchResult
from prototype.yixiang_adaptive_stopping_m41 import StopAudit, Decision
from prototype.yixiang_model_robustness_m42 import RobustnessAudit, RobustnessStatus
from prototype.yixiang_policy_transport_m43 import TransportAudit, TransportStatus
from prototype.yixiang_unified_adaptive_decision_m44 import PipelineInput, audit_pipeline

DATASET_VERSION = "m50-synthetic-confounded-scm-v0.1"
PROTOCOL_VERSION = "m50-paired-do-intervention-v0.1"
METRIC_SCHEMA_VERSION = "m47-v0.1"
CANDIDATES = ("a", "b", "c")
TARGET = "y"
POPULATION_SIZE = 64
INTERVENTION_BUDGET = 6


def _environment(seed):
    # q confounds a and c; only a and b are direct causes of y.
    spec = SCMSpec("m50-confounded-toy", (
        SCMNode("q", (), (), noise_scale=1.0),
        SCMNode("a", ("q",), (1.0,), noise_scale=0.25),
        SCMNode("b", (), (), noise_scale=1.0),
        SCMNode("c", ("q",), (1.0,), noise_scale=0.25),
        SCMNode("y", ("a", "b"), (2.0, 1.5), noise_scale=0.2),
    ), seed, POPULATION_SIZE)
    return SCMEnvironment(spec)


def _mean(rows, key):
    return sum(dict(row.values)[key] for row in rows) / len(rows)


def _intervention_effects(environment, unit_ids):
    effects = {}
    for candidate in CANDIDATES:
        zero = environment.sample(unit_ids, {candidate: 0.0})
        one = environment.sample(unit_ids, {candidate: 1.0})
        effects[candidate] = _mean(one, TARGET) - _mean(zero, TARGET)
    return effects


def _event(ledger, event_id, kind, run_id, payload, source, code_commit, seq):
    return ledger.append(
        event_id, kind, run_id, f"2026-11-14T08:{seq // 60:02d}:{seq % 60:02d}Z",
        payload, (source,), DATASET_VERSION, code_commit,
    )


def _m44_offline_preflight():
    # No M37-M43 evidence bundle is supplied by this synthetic offline benchmark.
    # M44 must therefore fail closed to human review and never authorize execution.
    policy = PolicyNode(None, (), (0.9,), 0)
    search = SearchResult(policy, (("seeded-policy", 0.9),), 0.9, 1,
                          "stop_policy", (), ())
    stopping = StopAudit(Decision.CONTINUE, 0.8, 0.9, 0.1, (), ())
    robustness = RobustnessAudit(RobustnessStatus.ROBUST_WITHIN_DECLARED_SET,
                                 0.9, 0.8, 0.9, 0.1, (("seeded-policy", 0.8),), (), ())
    transport = TransportAudit(TransportStatus.CONDITIONALLY_TRANSPORTABLE, 0.8, (), ())
    return audit_pipeline(PipelineInput(search, stopping, robustness, transport, ()))


def run_episode(seed, code_commit, episode_index):
    run_id = f"m50-episode-{episode_index}-seed-{seed}"
    environment = _environment(seed)
    unit_ids = tuple(range(POPULATION_SIZE))
    observational = environment.sample(unit_ids)
    ledger = EvidenceLedger()
    event_seq = 0

    effects = _intervention_effects(environment, unit_ids)
    for candidate in CANDIDATES:
        event_seq += 1
        _event(ledger, f"{run_id}-do-{candidate}", "action", run_id,
               {"operation": "do", "target": candidate, "values": [0.0, 1.0],
                "paired_unit_ids": list(unit_ids)}, f"protocol:{PROTOCOL_VERSION}",
               code_commit, event_seq)
        event_seq += 1
        _event(ledger, f"{run_id}-effect-{candidate}", "observation", run_id,
               {"candidate": candidate, "estimated_target_effect": effects[candidate],
                "estimator": "paired_population_mean_difference"},
               f"environment:{DATASET_VERSION}", code_commit, event_seq)

    agent_selected = tuple(sorted(CANDIDATES, key=lambda x: (-abs(effects[x]), x))[:2])
    random_selected = random_intervention_baseline(CANDIDATES, 2, seed=seed)
    correlation_selected = correlation_screen_baseline(
        tuple(dict(row.values) for row in observational), TARGET, CANDIDATES, 2
    )

    outputs = (
        BaselineOutput("intervention_agent_adapter", agent_selected, agent_selected,
                       2 * len(CANDIDATES) * POPULATION_SIZE, float(INTERVENTION_BUDGET),
                       True, True),
        BaselineOutput("seeded_random", random_selected, random_selected,
                       len(random_selected) * POPULATION_SIZE, float(len(random_selected)),
                       True, True),
        BaselineOutput("observational_correlation", correlation_selected,
                       correlation_selected, POPULATION_SIZE, 0.0, True, True),
    )
    # Oracle access is deliberately delayed until all candidate selections exist.
    truth = environment.oracle(TARGET)["direct_parents"]  # evaluator boundary only
    scores = []
    for output in outputs:
        score = evaluate_episode(truth, output.predicted_parents, output,
                                 INTERVENTION_BUDGET, min_interventions_for_commit=1)
        scores.append(score)
        event_seq += 1
        _event(ledger, f"{run_id}-{output.baseline_id}-decision", "policy_decision",
               run_id, {"baseline": output.baseline_id,
                        "selected": list(output.predicted_parents),
                        "budget": INTERVENTION_BUDGET,
                        "cost": output.total_cost},
               f"baseline:{output.baseline_id}", code_commit, event_seq)
        event_seq += 1
        _event(ledger, f"{run_id}-{output.baseline_id}-claim", "final_claim",
               run_id, {"baseline": output.baseline_id,
                        "predicted_direct_parents": list(output.predicted_parents),
                        "f1": score.f1, "shd": score.structural_hamming_distance},
               f"metric:{METRIC_SCHEMA_VERSION}", code_commit, event_seq)

    # The oracle is queried only after all agent-facing outputs have been produced.
    oracle_parents = oracle_diagnostic_baseline(truth)
    if tuple(sorted(oracle_parents)) != tuple(sorted(truth)):
        raise AssertionError("evaluator_oracle_invariant_failed")

    return {
        "episode_id": f"episode-{episode_index}",
        "seed": seed,
        "truth_parents_evaluator_only": tuple(sorted(truth)),
        "intervention_effects": effects,
        "outputs": outputs,
        "scores": tuple(scores),
        "score_by_id": {s.baseline_id: s for s in scores},
        "ledger": ledger,
        "ledger_audit": ledger.audit(),
        "oracle_diagnostic": {"baseline_id": "evaluator_oracle_only",
                              "predicted_parents": oracle_parents},
    }


def run_benchmark(episode_count=5, seed_start=7,
                  code_commit="abcdef1234567890abcdef1234567890abcdef12"):
    if not isinstance(episode_count, int) or episode_count < 2:
        raise ValueError("episode_count_must_be_at_least_two")
    if not isinstance(seed_start, int) or seed_start < 0:
        raise ValueError("seed_start_must_be_nonnegative")
    if len(code_commit) < 7 or any(c not in "0123456789abcdefABCDEF" for c in code_commit):
        raise ValueError("code_commit_must_be_hex_sha")
    preflight = _m44_offline_preflight()
    if preflight.execution_authorized or preflight.causal_truth_established:
        raise AssertionError("m44_preflight_must_not_authorize_offline_runner")
    episodes = tuple(run_episode(seed_start + i, code_commit, i)
                     for i in range(episode_count))
    all_scores = {name: [] for name in
                  ("intervention_agent_adapter", "seeded_random",
                   "observational_correlation")}
    full_runs = []
    ablation_runs = []
    for episode in episodes:
        for name, score in episode["score_by_id"].items():
            all_scores[name].append(score)
        full = episode["score_by_id"]["intervention_agent_adapter"]
        ablation = episode["score_by_id"]["observational_correlation"]
        full_runs.append(EpisodeRun("full", episode["episode_id"], episode["seed"],
                                    (("f1", full.f1),
                                     ("shd", float(full.structural_hamming_distance)))))
        ablation_runs.append(EpisodeRun("no_intervention", episode["episode_id"],
                                        episode["seed"],
                                        (("f1", ablation.f1),
                                         ("shd", float(ablation.structural_hamming_distance)))))

    ablation = compare_ablation(
        tuple(full_runs), tuple(ablation_runs),
        (MetricSpec("f1", True), MetricSpec("shd", False)),
        bootstrap_samples=1000, seed=seed_start,
    )
    summaries = {}
    for name, scores in all_scores.items():
        summaries[name] = {
            "episodes": len(scores),
            "mean_precision": sum(s.precision for s in scores) / len(scores),
            "mean_recall": sum(s.recall for s in scores) / len(scores),
            "mean_f1": sum(s.f1 for s in scores) / len(scores),
            "mean_shd": sum(s.structural_hamming_distance for s in scores) / len(scores),
            "mean_budget_utilization": sum(s.budget_utilization for s in scores) / len(scores),
            "budget_violation_rate": sum(s.budget_violation for s in scores) / len(scores),
            "trace_valid_rate": sum(s.trace_valid for s in scores) / len(scores),
        }

    ledger_records = [record for episode in episodes
                      for record in episode["ledger"].export_records()]
    ledger_digest = sha256("|".join(
        episode["ledger"].head_digest for episode in episodes
    ).encode("utf-8")).hexdigest()
    result_payload = {
        "protocol": PROTOCOL_VERSION, "seed_start": seed_start,
        "episode_count": episode_count, "summaries": summaries,
        "ablation_valid": ablation.valid,
        "ablation_effects": [asdict(x) for x in ablation.effects],
        "ledger_event_count": len(ledger_records),
    }
    artifact_digest = sha256(json.dumps(
        result_payload, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")).hexdigest()
    manifest = RunManifest(
        run_id=f"m50-run-{seed_start}-{episode_count}",
        code_commit=code_commit, clean_worktree=True,
        python_version="3.11+", platform="github-actions-ubuntu-latest",
        dependency_lock_ref="stdlib-only",
        dataset_version=DATASET_VERSION, benchmark_protocol=PROTOCOL_VERSION,
        config_digest=sha256(json.dumps(
            {"episode_count": episode_count, "seed_start": seed_start,
             "population_size": POPULATION_SIZE, "budget": INTERVENTION_BUDGET},
            sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest(),
        random_seed=seed_start,
        split_items=tuple(SplitItem(
            f"episode-{i}", "test", f"synthetic-scm-family-{seed_start+i}",
            f"synthetic-seed-family-{seed_start+i}"
        ) for i in range(episode_count)),
        artifacts=(ArtifactRef("m50-summary", "memory://m50/summary", artifact_digest),),
        event_ledger_digest=ledger_digest,
        metric_schema_version=METRIC_SCHEMA_VERSION,
    )
    manifest_audit = audit_manifest(manifest)
    return {
        "protocol": PROTOCOL_VERSION, "summaries": summaries,
        "m44_preflight": preflight,
        "paired_ablation": ablation, "episode_count": episode_count,
        "ledger_event_count": len(ledger_records),
        "ledger_valid": all(e["ledger_audit"].valid for e in episodes),
        "manifest_audit": manifest_audit, "manifest": manifest,
        "episodes": episodes, "result_digest": artifact_digest,
        "limitations": (
            "synthetic_linear_continuous_scm_only",
            "intervention_agent_is_a_handwritten_adapter_not_an_llm",
            "episode_families_are_test_only_no_training_or_model_selection_split",
            "ledger_is_in_memory_and_manifest_artifact_uri_is_a_placeholder",
            "oracle_is_evaluator_only_and_not_an_agent_input",
        ),
    }
