"""M32 composition of invariant candidates; local validity never entails whole-level validity."""
from dataclasses import dataclass
from enum import Enum
from typing import Tuple


class InvariantState(str, Enum):
    CANDIDATE = "candidate"
    INCONCLUSIVE = "inconclusive"
    BOUNDED = "bounded"
    REFUTED = "refuted"
    REPLICATED = "replicated"
    UNKNOWN = "unknown"


class CompositionKind(str, Enum):
    PARALLEL = "parallel"
    ORDERED = "ordered"
    CONTAINMENT = "containment"
    INTERACTION = "interaction"
    OPPOSITION = "opposition"
    TRANSFORMATION = "transformation"
    CONSTRAINT = "constraint"
    CONDITIONAL = "conditional"


class EvidenceLevel(str, Enum):
    MEMBER = "member"
    WHOLE = "whole"
    INTERACTION = "interaction"


class ReviewState(str, Enum):
    UNREVIEWED = "unreviewed"
    REVIEWED = "reviewed"
    DISPUTED = "disputed"


class CompositionDisposition(str, Enum):
    BLOCKED = "blocked"
    REVIEW_REQUIRED = "review_required"
    PROVISIONAL = "provisional"


@dataclass(frozen=True)
class InvariantSnapshot:
    invariant_id: str
    level: str
    state: str
    scope: str
    context_family: str
    object_family: str
    evidence_refs: Tuple[str, ...]


@dataclass(frozen=True)
class CompositionSpec:
    composition_id: str
    member_ids: Tuple[str, ...]
    kind: CompositionKind
    scope: str
    context_family: str
    ordered_member_ids: Tuple[str, ...] = ()
    boundary_conditions: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CompositionDependency:
    dependency_id: str
    source_invariant_id: str
    target_invariant_id: str
    composition_id: str
    kind: CompositionKind
    rationale: str


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_family_id: str
    context_family: str
    level: EvidenceLevel
    reviewed: ReviewState


@dataclass(frozen=True)
class EmergentInvariantClaim:
    claim_id: str
    composition_id: str
    whole_level: str
    operational_definition: str
    predicted_observable: str
    scope: str
    boundary_conditions: Tuple[str, ...]
    member_evidence_refs: Tuple[str, ...]
    whole_evidence_refs: Tuple[str, ...]
    interaction_evidence_refs: Tuple[str, ...]
    non_reducibility_argument: str
    counterexample_refs: Tuple[str, ...]
    competing_explanations: Tuple[str, ...]
    reviewer_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class CompositionCounterexample:
    counterexample_id: str
    composition_id: str
    description: str
    evidence_refs: Tuple[str, ...]
    review_state: ReviewState
    resolved_by: str = ""


@dataclass(frozen=True)
class CompositionEvaluation:
    evaluation_id: str
    train_object_families: Tuple[str, ...]
    test_object_families: Tuple[str, ...]
    train_context_families: Tuple[str, ...]
    test_context_families: Tuple[str, ...]
    train_composition_ids: Tuple[str, ...]
    test_composition_ids: Tuple[str, ...]
    train_source_families: Tuple[str, ...]
    test_source_families: Tuple[str, ...]
    baselines: Tuple[str, ...]
    metrics: Tuple[str, ...]
    results_ref: str
    sample_size: int
    configuration_ref: str
    limitations: Tuple[str, ...]


@dataclass(frozen=True)
class CompositionAudit:
    valid: bool
    disposition: CompositionDisposition
    issues: Tuple[str, ...]
    claim_dispositions: Tuple[Tuple[str, str], ...]
    semantic_truth_established: bool = False


def audit_invariant_composition_m32(
    invariants, compositions, dependencies=(), evidence=(), claims=(),
    counterexamples=(), evaluations=(),
):
    invariants = tuple(invariants)
    compositions = tuple(compositions)
    dependencies = tuple(dependencies)
    evidence = tuple(evidence)
    claims = tuple(claims)
    counterexamples = tuple(counterexamples)
    evaluations = tuple(evaluations)
    issues = []
    needs_review = False

    imap = {x.invariant_id: x for x in invariants}
    cmap = {x.composition_id: x for x in compositions}
    emap = {x.evidence_id: x for x in evidence}
    if len(imap) != len(invariants): issues.append("duplicate_invariant_id")
    if len(cmap) != len(compositions): issues.append("duplicate_composition_id")
    if len(emap) != len(evidence): issues.append("duplicate_evidence_id")

    allowed_states = {x.value for x in InvariantState}
    for inv in invariants:
        if not all((inv.invariant_id, inv.level, inv.scope, inv.context_family,
                    inv.object_family)) or not inv.evidence_refs:
            issues.append("incomplete_invariant:" + inv.invariant_id)
        if inv.state not in allowed_states:
            issues.append("unknown_invariant_state:" + inv.invariant_id)
        if inv.state == InvariantState.REFUTED.value:
            issues.append("refuted_member_in_composition_pool:" + inv.invariant_id)
        if inv.state in (InvariantState.CANDIDATE.value, InvariantState.INCONCLUSIVE.value,
                         InvariantState.UNKNOWN.value):
            needs_review = True

    for ev in evidence:
        if not all((ev.evidence_id, ev.source_family_id, ev.context_family)):
            issues.append("incomplete_evidence:" + ev.evidence_id)

    for comp in compositions:
        if not comp.composition_id or len(comp.member_ids) < 2:
            issues.append("composition_requires_two_members:" + comp.composition_id)
        if len(set(comp.member_ids)) != len(comp.member_ids):
            issues.append("duplicate_composition_member:" + comp.composition_id)
        if not comp.scope or not comp.context_family or not comp.boundary_conditions:
            issues.append("incomplete_composition_scope_or_boundary:" + comp.composition_id)
        for mid in comp.member_ids:
            member = imap.get(mid)
            if member is None:
                issues.append("unknown_composition_member:" + comp.composition_id + ":" + mid)
            elif member.context_family != comp.context_family:
                issues.append("member_context_family_mismatch:" + comp.composition_id + ":" + mid)
        if comp.kind == CompositionKind.ORDERED:
            if len(comp.ordered_member_ids) != len(comp.member_ids) or set(comp.ordered_member_ids) != set(comp.member_ids):
                issues.append("ordered_composition_requires_permutation:" + comp.composition_id)
        elif comp.ordered_member_ids:
            issues.append("order_declared_for_unordered_composition:" + comp.composition_id)

    dep_ids = [d.dependency_id for d in dependencies]
    if len(dep_ids) != len(set(dep_ids)): issues.append("duplicate_dependency_id")
    graph = {}
    for dep in dependencies:
        comp = cmap.get(dep.composition_id)
        if dep.source_invariant_id not in imap or dep.target_invariant_id not in imap:
            issues.append("unknown_dependency_endpoint:" + dep.dependency_id)
        if comp is None:
            issues.append("unknown_dependency_composition:" + dep.dependency_id)
        elif (dep.source_invariant_id not in comp.member_ids or
              dep.target_invariant_id not in comp.member_ids):
            issues.append("dependency_endpoint_outside_composition:" + dep.dependency_id)
        if dep.source_invariant_id == dep.target_invariant_id:
            issues.append("self_dependency:" + dep.dependency_id)
        if not dep.rationale.strip():
            issues.append("missing_dependency_rationale:" + dep.dependency_id)
        graph.setdefault(dep.source_invariant_id, []).append(dep.target_invariant_id)

    visiting, visited = set(), set()
    def cyclic(node):
        if node in visiting: return True
        if node in visited: return False
        visiting.add(node)
        found = any(cyclic(nxt) for nxt in graph.get(node, ()))
        visiting.remove(node)
        visited.add(node)
        return found
    if any(cyclic(node) for node in tuple(graph)):
        issues.append("composition_dependency_cycle")

    cex_map = {}
    cex_ids = [x.counterexample_id for x in counterexamples]
    if len(cex_ids) != len(set(cex_ids)): issues.append("duplicate_counterexample_id")
    for cex in counterexamples:
        if cex.composition_id not in cmap or not cex.description.strip() or not cex.evidence_refs:
            issues.append("incomplete_composition_counterexample:" + cex.counterexample_id)
        if any(ref not in emap for ref in cex.evidence_refs):
            issues.append("unknown_counterexample_evidence:" + cex.counterexample_id)
        cex_map.setdefault(cex.composition_id, []).append(cex)

    claim_ids = [x.claim_id for x in claims]
    if len(claim_ids) != len(set(claim_ids)): issues.append("duplicate_claim_id")
    claim_states = []
    for claim in claims:
        comp = cmap.get(claim.composition_id)
        if comp is None:
            issues.append("unknown_claim_composition:" + claim.claim_id)
            claim_states.append((claim.claim_id, "blocked"))
            continue
        if not all((claim.whole_level, claim.operational_definition.strip(),
                    claim.predicted_observable.strip(), claim.scope.strip(),
                    claim.non_reducibility_argument.strip())):
            issues.append("incomplete_emergent_claim:" + claim.claim_id)
        if len(set(claim.member_evidence_refs)) != len(claim.member_evidence_refs):
            issues.append("duplicate_member_evidence_ref:" + claim.claim_id)
        if not claim.member_evidence_refs or not claim.whole_evidence_refs:
            issues.append("member_and_whole_evidence_required:" + claim.claim_id)
        if not claim.interaction_evidence_refs and comp.kind in (
            CompositionKind.INTERACTION, CompositionKind.CONSTRAINT,
            CompositionKind.CONDITIONAL, CompositionKind.TRANSFORMATION
        ):
            issues.append("interaction_evidence_required:" + claim.claim_id)
        groups = [claim.member_evidence_refs, claim.whole_evidence_refs,
                  claim.interaction_evidence_refs]
        if set(groups[0]) & set(groups[1]) or set(groups[0]) & set(groups[2]) or set(groups[1]) & set(groups[2]):
            issues.append("evidence_level_overlap:" + claim.claim_id)
        all_refs = set().union(*map(set, groups))
        if any(ref not in emap for ref in all_refs):
            issues.append("unknown_claim_evidence:" + claim.claim_id)
        else:
            for ref in claim.member_evidence_refs:
                if emap[ref].level != EvidenceLevel.MEMBER:
                    issues.append("member_evidence_level_mismatch:" + claim.claim_id)
            for ref in claim.whole_evidence_refs:
                if emap[ref].level != EvidenceLevel.WHOLE:
                    issues.append("whole_evidence_level_mismatch:" + claim.claim_id)
            for ref in claim.interaction_evidence_refs:
                if emap[ref].level != EvidenceLevel.INTERACTION:
                    issues.append("interaction_evidence_level_mismatch:" + claim.claim_id)
            source_families = [emap[r].source_family_id for r in claim.whole_evidence_refs]
            if len(source_families) != len(set(source_families)):
                issues.append("whole_evidence_shared_source_family:" + claim.claim_id)
            if any(emap[r].reviewed != ReviewState.REVIEWED for r in all_refs):
                needs_review = True
        if claim.scope != comp.scope or not set(claim.boundary_conditions).issuperset(set(comp.boundary_conditions)):
            issues.append("claim_scope_or_boundary_mismatch:" + claim.claim_id)
        if set(claim.counterexample_refs) != {x.counterexample_id for x in cex_map.get(comp.composition_id, ())}:
            # The claim must explicitly account for every recorded counterexample.
            needs_review = True
        if not claim.competing_explanations or not claim.reviewer_ids:
            needs_review = True
            issues.append("claim_requires_competitors_and_reviewers:" + claim.claim_id)
        unresolved = [x for x in cex_map.get(comp.composition_id, ())
                      if x.review_state == ReviewState.REVIEWED and not x.resolved_by]
        if unresolved:
            issues.append("unresolved_reviewed_counterexample:" + claim.claim_id)
        # Local member state is deliberately not promoted to a whole-level state.
        if claim.whole_evidence_refs and claim.non_reducibility_argument.strip() and not unresolved:
            claim_states.append((claim.claim_id, "review_required"))
            needs_review = True
        else:
            claim_states.append((claim.claim_id, "blocked"))

    for ev in evaluations:
        if set(ev.train_object_families) & set(ev.test_object_families):
            issues.append("object_family_leakage:" + ev.evaluation_id)
        if set(ev.train_context_families) & set(ev.test_context_families):
            issues.append("context_family_leakage:" + ev.evaluation_id)
        if set(ev.train_composition_ids) & set(ev.test_composition_ids):
            issues.append("composition_leakage:" + ev.evaluation_id)
        if set(ev.train_source_families) & set(ev.test_source_families):
            issues.append("source_family_leakage:" + ev.evaluation_id)
        required = {"member_prediction", "local_composition", "structural_relation", "whole_level"}
        if not required.issubset(set(ev.baselines)):
            issues.append("missing_composition_baselines:" + ev.evaluation_id)
        if not ev.metrics or not ev.results_ref or ev.sample_size <= 0 or not ev.configuration_ref or not ev.limitations:
            issues.append("incomplete_composition_evaluation:" + ev.evaluation_id)

    valid = not issues
    disposition = (CompositionDisposition.BLOCKED if not valid else
                   CompositionDisposition.REVIEW_REQUIRED if needs_review or claims else
                   CompositionDisposition.PROVISIONAL)
    return CompositionAudit(valid, disposition, tuple(sorted(set(issues))),
                            tuple(sorted(claim_states)), False)
