"""Durable E12-A6 lifecycle ledger backed by ZPCM's append-only event log."""
from __future__ import annotations
from copy import deepcopy
import json
from datetime import datetime
from dataclasses import dataclass, replace
from threading import RLock
from typing import Any, Mapping
from prototype.e12a6_lifecycle_contract import Action, ActionType, Candidate, CandidateState, Evidence, LifecycleLedger, SplitRole
from prototype.e09_verification_receipt import VerifiedE09VerificationReceipt
from prototype.zpcm_memory import ZPCMMemory

EVENT_SCHEMA = "e12a6-lifecycle-event-v1"

class LifecyclePersistenceError(RuntimeError):
    """A persisted lifecycle stream cannot be safely reconstructed."""

@dataclass(frozen=True)
class LifecycleEventReceipt:
    event_id: str
    sequence: int
    payload_digest: str
    replayed: bool = False

@dataclass(frozen=True)
class LifecycleBundleReceipt:
    candidate: LifecycleEventReceipt
    evidence: tuple[LifecycleEventReceipt, ...]
    replayed: bool = False
    authorization: LifecycleEventReceipt | None = None

def _candidate_to_dict(v: Candidate) -> dict[str, Any]:
    return {"candidate_id":v.candidate_id,"version":v.version,"canonical_expression":v.canonical_expression,
      "proposer_family":v.proposer_family,"supporting_families":list(v.supporting_families),
      "input_types":list(v.input_types),"operator":v.operator,"conditions":list(v.conditions),
      "uncertainty":v.uncertainty,"complexity":v.complexity,"proposal_cost":v.proposal_cost,
      "parent_refs":list(v.parent_refs),"evidence_ids":list(v.evidence_ids),"state":v.state.value}

def _candidate_from_dict(v: dict[str, Any]) -> Candidate:
    d=dict(v)
    for k in ("supporting_families","input_types","conditions","parent_refs","evidence_ids"): d[k]=tuple(d.get(k,()))
    d["state"]=CandidateState(d["state"])
    return Candidate(**d)

def _evidence_to_dict(v: Evidence) -> dict[str, Any]:
    return {"evidence_id":v.evidence_id,"episode_id":v.episode_id,"world_family":v.world_family,
      "split_role":v.split_role.value,"observation_id":v.observation_id,"outcome":v.outcome,
      "model_version":v.model_version,"measurement_cost":v.measurement_cost,
      "prediction_commit_step":v.prediction_commit_step,"label_visibility_step":v.label_visibility_step,
      "provenance":v.provenance,"domain_id":v.domain_id,
      "domain_registry_id":v.domain_registry_id,"domain_registry_version":v.domain_registry_version}

def _evidence_from_dict(v: dict[str, Any]) -> Evidence:
    d=dict(v); d["split_role"]=SplitRole(d["split_role"]); return Evidence(**d)

def _action_to_dict(v: Action) -> dict[str, Any]:
    return {"action_id":v.action_id,"action_type":v.action_type.value,"candidate_id":v.candidate_id,
      "candidate_version":v.candidate_version,"evidence_ids":list(v.evidence_ids),"cost":v.cost,
      "from_state":v.from_state.value if v.from_state else None,
      "to_state":v.to_state.value if v.to_state else None,"note":v.note}

def _action_from_dict(v: dict[str, Any]) -> Action:
    d=dict(v); d["action_type"]=ActionType(d["action_type"])
    d["evidence_ids"]=tuple(d.get("evidence_ids",()))
    d["from_state"]=CandidateState(d["from_state"]) if d.get("from_state") else None
    d["to_state"]=CandidateState(d["to_state"]) if d.get("to_state") else None
    return Action(**d)


def _safe_evidence(evidence: Evidence) -> Evidence:
    # E12-A6 consumes split/provenance metadata; E09 retains raw target values.
    return replace(
        evidence,
        outcome=f"opaque-evidence-ref:{evidence.evidence_id}",
        provenance=f"opaque-provenance-ref:{evidence.evidence_id}",
    )

class PersistentLifecycleLedger:
    """E12 validates; ZPCM persists immutable events; replay revalidates transitions."""
    def __init__(self, memory: ZPCMMemory, *, scope: str) -> None:
        if not isinstance(memory,ZPCMMemory): raise TypeError("memory must be ZPCMMemory")
        if not isinstance(scope,str) or not scope.strip(): raise ValueError("scope required")
        self._memory=memory; self.scope=scope; self._lock=RLock()
        self._ledger=LifecycleLedger(); self._last_sequence=0
        self._receipts={}; self._event_payloads={}; self._consumed_receipts={}
        self._restore()

    @property
    def ledger(self) -> LifecycleLedger:
        with self._lock: return deepcopy(self._ledger)

    def _restore(self) -> None:
        try:
            events=self._memory.replay_lifecycle_events(scope=self.scope)
            staged=LifecycleLedger(); previous=0; receipts={}; payloads={}; consumed_receipts={}; consumed_nonces=set()
            for event in events:
                seq=event["sequence"]
                if isinstance(seq,bool) or not isinstance(seq,int) or seq<=previous:
                    raise LifecyclePersistenceError("event sequence is not strictly increasing")
                previous=seq; payload=event["payload"]
                if payload.get("schema_version")!=EVENT_SCHEMA:
                    raise LifecyclePersistenceError("unsupported lifecycle event schema")
                kind=payload.get("kind"); body=payload.get("body")
                if not isinstance(body,dict): raise LifecyclePersistenceError("event body must be an object")
                if kind=="candidate_registered": staged.add_candidate(_candidate_from_dict(body["candidate"]))
                elif kind=="evidence_registered": staged.add_evidence(_evidence_from_dict(body["evidence"]))
                elif kind=="action_applied": staged.apply(_action_from_dict(body["action"]))
                elif kind=="revision_created":
                    args=dict(body["arguments"])
                    for k in ("conditions","supporting_families","input_types","evidence_ids"): args[k]=tuple(args.get(k,()))
                    made=staged.create_revision(**args)
                    if _candidate_to_dict(made)!=body["candidate"]:
                        raise LifecyclePersistenceError("revision replay mismatch")
                elif kind=="authorization_consumed":
                    required = {
                        "receipt_id", "nonce", "authorization_ref", "episode_id", "scope",
                        "parent_state_ref", "branch_ids", "authorization_evidence_refs",
                        "evidence_refs", "issuer_id", "verifier_id", "authorization_event_digest",
                        "receipt_issued_at", "receipt_expires_at", "candidate_id", "candidate_version", "consumed_at",
                        "submitter_workload_id", "submitter_identity_provider",
                        "submitter_authentication_method", "submitter_credential_fingerprint",
                    }
                    if set(body) != required:
                        raise LifecyclePersistenceError("authorization consumption has an invalid schema")
                    receipt_id, nonce = body["receipt_id"], body["nonce"]
                    if (not isinstance(receipt_id, str) or not receipt_id.strip()
                            or not isinstance(nonce, str) or not nonce.strip()
                            or receipt_id in consumed_receipts or nonce in consumed_nonces):
                        raise LifecyclePersistenceError("authorization receipt or nonce was consumed more than once")
                    if body["scope"] != self.scope:
                        raise LifecyclePersistenceError("authorization consumption scope mismatch")
                    candidate = staged.candidates.get((body["candidate_id"], body["candidate_version"]))
                    if candidate is None:
                        raise LifecyclePersistenceError("authorization consumed before candidate registration")
                    if set(body["evidence_refs"]) != set(candidate.evidence_ids):
                        raise LifecyclePersistenceError("authorization evidence does not cover candidate evidence")
                    if any(ref not in staged.evidence for ref in body["evidence_refs"]):
                        raise LifecyclePersistenceError("authorization consumed before evidence registration")
                    if any(staged.evidence[ref].episode_id != body["episode_id"] for ref in body["evidence_refs"]):
                        raise LifecyclePersistenceError("authorization receipt evidence episode mismatch")
                    try:
                        definition = json.loads(candidate.canonical_expression)
                        merge = definition["branch_merge"]
                        consumed_at = datetime.fromisoformat(body["consumed_at"].replace("Z", "+00:00"))
                        receipt_issued_at = datetime.fromisoformat(body["receipt_issued_at"].replace("Z", "+00:00"))
                        receipt_expires_at = datetime.fromisoformat(body["receipt_expires_at"].replace("Z", "+00:00"))
                    except (TypeError, ValueError, KeyError) as exc:
                        raise LifecyclePersistenceError("authorization candidate binding is malformed") from exc
                    identity_fields = (
                        "submitter_workload_id", "submitter_identity_provider",
                        "submitter_authentication_method", "submitter_credential_fingerprint",
                    )
                    if any(not isinstance(body.get(field), str) or not body[field].strip() for field in identity_fields):
                        raise LifecyclePersistenceError("authorization consumption submitter identity is incomplete")
                    if (len(body["submitter_credential_fingerprint"]) != 64
                            or any(char not in "0123456789abcdef" for char in body["submitter_credential_fingerprint"])):
                        raise LifecyclePersistenceError("authorization consumption submitter fingerprint is invalid")
                    if (not isinstance(merge, dict)
                            or merge.get("authorization_ref") != body["authorization_ref"]
                            or set(definition.get("branch_ids", ())) != set(body["branch_ids"])
                            or set(merge.get("authorization_evidence_refs", ())) != set(body["authorization_evidence_refs"])
                            or body["parent_state_ref"] not in candidate.parent_refs
                            or consumed_at.tzinfo is None or receipt_issued_at.tzinfo is None
                            or receipt_expires_at.tzinfo is None
                            or consumed_at < receipt_issued_at or consumed_at >= receipt_expires_at):
                        raise LifecyclePersistenceError("authorization consumption does not bind the candidate merge")
                    if event["event_id"] != f"e12a6:authorization-consumed:{receipt_id}":
                        raise LifecyclePersistenceError("authorization consumption event ID mismatch")
                    consumed_receipts[receipt_id] = body
                    consumed_nonces.add(nonce)
                else: raise LifecyclePersistenceError(f"unknown lifecycle event kind: {kind!r}")
                eid=event["event_id"]
                receipts[eid]=LifecycleEventReceipt(eid,seq,event["payload_digest"],True)
                payloads[eid]=payload
            self._ledger=staged; self._last_sequence=previous
            self._receipts=receipts; self._event_payloads=payloads; self._consumed_receipts=consumed_receipts
        except LifecyclePersistenceError: raise
        except Exception as exc: raise LifecyclePersistenceError(f"lifecycle replay failed: {exc}") from exc

    def _commit(self,event_id: str,payload: dict[str,Any],staged: LifecycleLedger) -> LifecycleEventReceipt:
        raw=self._memory.append_lifecycle_event(event_id=event_id,scope=self.scope,
          payload=payload,expected_sequence=self._last_sequence)
        receipt=LifecycleEventReceipt(event_id,raw["sequence"],raw["payload_digest"],raw["replayed"])
        if receipt.replayed:
            if self._event_payloads.get(event_id)!=payload:
                raise LifecyclePersistenceError("replayed event differs from local history")
            return receipt
        self._ledger=staged; self._last_sequence=receipt.sequence
        self._receipts[event_id]=receipt; self._event_payloads[event_id]=payload
        return receipt

    def register_candidate(self,candidate: Candidate) -> LifecycleEventReceipt:
        eid=f"e12a6:candidate:{candidate.candidate_id}@{candidate.version}"
        payload={"schema_version":EVENT_SCHEMA,"kind":"candidate_registered","body":{"candidate":_candidate_to_dict(candidate)}}
        with self._lock:
            key=(candidate.candidate_id,candidate.version); old=self._ledger.candidates.get(key)
            if old is not None:
                if old!=candidate or self._event_payloads.get(eid)!=payload: raise LifecyclePersistenceError("candidate ID content conflict")
                r=self._receipts[eid]; return LifecycleEventReceipt(r.event_id,r.sequence,r.payload_digest,True)
            staged=deepcopy(self._ledger); staged.add_candidate(candidate)
            return self._commit(eid,payload,staged)

    def register_evidence(self,evidence: Evidence) -> LifecycleEventReceipt:
        safe_evidence = _safe_evidence(evidence)
        eid=f"e12a6:evidence:{safe_evidence.evidence_id}"
        payload={"schema_version":EVENT_SCHEMA,"kind":"evidence_registered","body":{"evidence":_evidence_to_dict(safe_evidence)}}
        with self._lock:
            old=self._ledger.evidence.get(safe_evidence.evidence_id)
            if old is not None:
                if old!=safe_evidence or self._event_payloads.get(eid)!=payload: raise LifecyclePersistenceError("evidence ID content conflict")
                r=self._receipts[eid]; return LifecycleEventReceipt(r.event_id,r.sequence,r.payload_digest,True)
            staged=deepcopy(self._ledger); staged.add_evidence(safe_evidence)
            return self._commit(eid,payload,staged)


    def register_candidate_bundle(
        self,
        candidate: Candidate,
        evidence: tuple[Evidence, ...] | list[Evidence],
        *,
        authorization_receipt: VerifiedE09VerificationReceipt | None = None,
        consumed_at: datetime | None = None,
        writer_identity: Mapping[str, str] | None = None,
    ) -> LifecycleBundleReceipt:
        """Atomically register a candidate/evidence bundle and consume its verifier receipt."""
        if not isinstance(candidate, Candidate):
            raise TypeError("candidate must be Candidate")
        if not isinstance(evidence, (tuple, list)) or any(not isinstance(x, Evidence) for x in evidence):
            raise TypeError("evidence must be a sequence of Evidence")
        safe_evidence = tuple(sorted((_safe_evidence(x) for x in evidence), key=lambda x: x.evidence_id))
        evidence_ids = [x.evidence_id for x in safe_evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise LifecyclePersistenceError("candidate bundle contains duplicate evidence IDs")
        candidate_id = f"e12a6:candidate:{candidate.candidate_id}@{candidate.version}"
        candidate_payload = {
            "schema_version": EVENT_SCHEMA, "kind": "candidate_registered",
            "body": {"candidate": _candidate_to_dict(candidate)},
        }
        evidence_events = [
            (
                f"e12a6:evidence:{item.evidence_id}",
                {"schema_version": EVENT_SCHEMA, "kind": "evidence_registered",
                 "body": {"evidence": _evidence_to_dict(item)}},
            )
            for item in safe_evidence
        ]

        authorization_event = None
        authorization_body = None
        if authorization_receipt is None:
            if consumed_at is not None or writer_identity is not None:
                raise LifecyclePersistenceError("receipt consumption metadata requires a verified authorization receipt")
        else:
            if not isinstance(authorization_receipt, VerifiedE09VerificationReceipt):
                raise TypeError("authorization_receipt must be a VerifiedE09VerificationReceipt")
            if not isinstance(consumed_at, datetime) or consumed_at.tzinfo is None:
                raise LifecyclePersistenceError("receipt consumption requires timezone-aware writer time")
            receipt = authorization_receipt
            identity_fields = {
                "workload_id", "identity_provider", "authentication_method", "credential_fingerprint",
            }
            if not isinstance(writer_identity, Mapping) or set(writer_identity) != identity_fields:
                raise LifecyclePersistenceError("receipt consumption requires authenticated writer identity")
            if any(not isinstance(writer_identity[field], str) or not writer_identity[field].strip()
                   for field in identity_fields):
                raise LifecyclePersistenceError("authenticated writer identity fields must be non-empty strings")
            fingerprint = writer_identity["credential_fingerprint"]
            if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
                raise LifecyclePersistenceError("writer credential fingerprint must be lowercase SHA-256")
            consumed_at = consumed_at.astimezone(receipt.expires_at.tzinfo)
            if receipt.scope != self.scope:
                raise LifecyclePersistenceError("authorization receipt scope does not match lifecycle ledger")
            if consumed_at < receipt.issued_at or consumed_at >= receipt.expires_at:
                raise LifecyclePersistenceError("authorization receipt is not valid at consumption time")
            if (len(set(receipt.evidence_refs)) != len(receipt.evidence_refs)
                    or set(receipt.evidence_refs) != set(evidence_ids)):
                raise LifecyclePersistenceError("authorization receipt does not cover the candidate evidence bundle")
            if (not set(receipt.authorization_evidence_refs).issubset(set(receipt.evidence_refs))
                    or len(set(receipt.branch_ids)) != len(receipt.branch_ids)):
                raise LifecyclePersistenceError("authorization receipt branch/evidence bindings are invalid")
            if {item.evidence_id for item in receipt.evidence} != set(evidence_ids):
                raise LifecyclePersistenceError("authorization receipt evidence DTOs do not match bundle evidence")
            if any(item.episode_id != receipt.episode_id for item in receipt.evidence):
                raise LifecyclePersistenceError("receipt DTO episode differs from receipt")
            if any(item.episode_id != receipt.episode_id for item in safe_evidence):
                raise LifecyclePersistenceError("candidate evidence episode differs from authorization receipt")
            try:
                definition = json.loads(candidate.canonical_expression)
                merge = definition["branch_merge"]
            except (TypeError, ValueError, KeyError) as exc:
                raise LifecyclePersistenceError("authorized candidate must contain a typed branch merge definition") from exc
            if (not isinstance(merge, dict)
                    or merge.get("authorization_ref") != receipt.authorization_ref
                    or set(definition.get("branch_ids", ())) != set(receipt.branch_ids)
                    or set(merge.get("authorization_evidence_refs", ())) != set(receipt.authorization_evidence_refs)
                    or receipt.parent_state_ref not in candidate.parent_refs):
                raise LifecyclePersistenceError("authorization receipt does not bind the candidate branch merge")
            authorization_body = {
                "receipt_id": receipt.receipt_id,
                "nonce": receipt.nonce,
                "authorization_ref": receipt.authorization_ref,
                "episode_id": receipt.episode_id,
                "scope": receipt.scope,
                "parent_state_ref": receipt.parent_state_ref,
                "branch_ids": list(receipt.branch_ids),
                "authorization_evidence_refs": list(receipt.authorization_evidence_refs),
                "evidence_refs": list(receipt.evidence_refs),
                "issuer_id": receipt.issuer_id,
                "verifier_id": receipt.verifier_id,
                "authorization_event_digest": receipt.authorization_event_digest,
                "receipt_issued_at": receipt.issued_at.isoformat(),
                "receipt_expires_at": receipt.expires_at.isoformat(),
                "candidate_id": candidate.candidate_id,
                "candidate_version": candidate.version,
                "consumed_at": consumed_at.isoformat(),
                "submitter_workload_id": writer_identity["workload_id"],
                "submitter_identity_provider": writer_identity["identity_provider"],
                "submitter_authentication_method": writer_identity["authentication_method"],
                "submitter_credential_fingerprint": writer_identity["credential_fingerprint"],
            }
            prior_receipt_use = self._consumed_receipts.get(receipt.receipt_id)
            if prior_receipt_use is not None:
                prior_binding = dict(prior_receipt_use)
                current_binding = dict(authorization_body)
                prior_binding.pop("consumed_at", None)
                current_binding.pop("consumed_at", None)
                if prior_binding != current_binding:
                    raise LifecyclePersistenceError("authorization receipt was already consumed for another binding")
                authorization_body["consumed_at"] = prior_receipt_use["consumed_at"]
            authorization_event = (
                f"e12a6:authorization-consumed:{receipt.receipt_id}",
                {"schema_version": EVENT_SCHEMA, "kind": "authorization_consumed",
                 "body": authorization_body},
            )

        events = [
            {"event_id": event_id, "payload": payload}
            for event_id, payload in evidence_events
        ]
        events.append({"event_id": candidate_id, "payload": candidate_payload})
        if authorization_event is not None:
            events.append({"event_id": authorization_event[0], "payload": authorization_event[1]})

        with self._lock:
            if authorization_receipt is not None:
                prior_use = self._consumed_receipts.get(authorization_receipt.receipt_id)
                nonce_used = any(
                    body.get("nonce") == authorization_receipt.nonce
                    for body in self._consumed_receipts.values()
                )
                if ((prior_use is not None and prior_use != authorization_body)
                        or (nonce_used and prior_use is None)):
                    raise LifecyclePersistenceError("authorization receipt or nonce was already consumed")
            key = (candidate.candidate_id, candidate.version)
            old_candidate = self._ledger.candidates.get(key)
            old_evidence = [self._ledger.evidence.get(item.evidence_id) for item in safe_evidence]
            present = [old_candidate is not None] + [item is not None for item in old_evidence]
            if any(present):
                if not all(present):
                    raise LifecyclePersistenceError("partial candidate bundle already exists")
                if old_candidate != candidate or any(
                    old != item for old, item in zip(old_evidence, safe_evidence)
                ):
                    raise LifecyclePersistenceError("candidate bundle identity/content conflict")
                prior_consumptions = [
                    body for body in self._consumed_receipts.values()
                    if body.get("candidate_id") == candidate.candidate_id
                    and body.get("candidate_version") == candidate.version
                ]
                if prior_consumptions and authorization_receipt is None:
                    raise LifecyclePersistenceError("receipt-backed candidate replay requires the same receipt")
                expected_payloads = dict(evidence_events + [(candidate_id, candidate_payload)])
                if authorization_event is not None:
                    expected_payloads[authorization_event[0]] = authorization_event[1]
                if any(self._event_payloads.get(eid) != payload for eid, payload in expected_payloads.items()):
                    raise LifecyclePersistenceError("candidate bundle event history mismatch")
                evidence_receipts = tuple(
                    LifecycleEventReceipt(
                        self._receipts[eid].event_id, self._receipts[eid].sequence,
                        self._receipts[eid].payload_digest, True,
                    )
                    for eid, _ in evidence_events
                )
                prior = self._receipts[candidate_id]
                auth_receipt = None
                if authorization_event is not None:
                    auth = self._receipts[authorization_event[0]]
                    auth_receipt = LifecycleEventReceipt(
                        auth.event_id, auth.sequence, auth.payload_digest, True,
                    )
                return LifecycleBundleReceipt(
                    LifecycleEventReceipt(prior.event_id, prior.sequence, prior.payload_digest, True),
                    evidence_receipts, True, auth_receipt,
                )

            staged = deepcopy(self._ledger)
            for item in safe_evidence:
                staged.add_evidence(item)
            staged.add_candidate(candidate)
            raw_receipts = self._memory.append_lifecycle_events(
                events=events, scope=self.scope, expected_sequence=self._last_sequence,
            )
            receipts = {
                raw["event_id"]: LifecycleEventReceipt(
                    raw["event_id"], raw["sequence"], raw["payload_digest"], raw["replayed"],
                )
                for raw in raw_receipts
            }
            if any(item.replayed for item in receipts.values()):
                raise LifecyclePersistenceError(
                    "bundle already exists in ZPCM outside this adapter; reconstruct ledger before retry"
                )
            self._ledger = staged
            self._last_sequence = raw_receipts[-1]["sequence"]
            for event_id, payload in evidence_events + [(candidate_id, candidate_payload)]:
                self._receipts[event_id] = receipts[event_id]
                self._event_payloads[event_id] = payload
            auth_receipt = None
            if authorization_event is not None:
                auth_event_id, auth_payload = authorization_event
                self._receipts[auth_event_id] = receipts[auth_event_id]
                self._event_payloads[auth_event_id] = auth_payload
                self._consumed_receipts[authorization_receipt.receipt_id] = authorization_body
                auth_receipt = receipts[auth_event_id]
            return LifecycleBundleReceipt(
                receipts[candidate_id],
                tuple(receipts[event_id] for event_id, _ in evidence_events),
                False,
                auth_receipt,
            )

    def apply(self,action: Action) -> LifecycleEventReceipt:
        eid=f"e12a6:action:{action.action_id}"
        payload={"schema_version":EVENT_SCHEMA,"kind":"action_applied","body":{"action":_action_to_dict(action)}}
        with self._lock:
            if action.action_id in self._ledger._action_ids:
                r=self._receipts.get(eid)
                if r is None or self._event_payloads.get(eid)!=payload: raise LifecyclePersistenceError("action ID content conflict")
                return LifecycleEventReceipt(r.event_id,r.sequence,r.payload_digest,True)
            staged=deepcopy(self._ledger); staged.apply(action)
            return self._commit(eid,payload,staged)

    def create_revision(self,candidate_id: str,version: int,**kwargs: Any):
        args=dict(kwargs)
        for k in ("conditions","supporting_families","input_types","evidence_ids"):
            if k in args: args[k]=tuple(args[k])
        eid=f"e12a6:revision:{candidate_id}@{version+1}"
        with self._lock:
            existing=self._ledger.candidates.get((candidate_id,version+1))
            if existing is not None:
                recorded={"candidate_id":candidate_id,"version":version,**args}
                recorded={k:list(v) if isinstance(v,tuple) else v for k,v in recorded.items()}
                expected={"schema_version":EVENT_SCHEMA,"kind":"revision_created",
                  "body":{"arguments":recorded,"candidate":_candidate_to_dict(existing)}}
                if self._event_payloads.get(eid)!=expected:
                    raise LifecyclePersistenceError("revision identity reused with different content")
                r=self._receipts[eid]
                return existing,LifecycleEventReceipt(r.event_id,r.sequence,r.payload_digest,True)
            staged=deepcopy(self._ledger); made=staged.create_revision(candidate_id,version,**args)
            recorded={"candidate_id":candidate_id,"version":version,**args}
            recorded={k:list(v) if isinstance(v,tuple) else v for k,v in recorded.items()}
            payload={"schema_version":EVENT_SCHEMA,"kind":"revision_created",
              "body":{"arguments":recorded,"candidate":_candidate_to_dict(made)}}
            receipt=self._commit(eid,payload,staged)
            return made,receipt

    def snapshot(self) -> dict[str,Any]:
        with self._lock:
            return {"schema_version":EVENT_SCHEMA,"scope":self.scope,"last_sequence":self._last_sequence,
              "candidates":[_candidate_to_dict(v) for _,v in sorted(self._ledger.candidates.items())],
              "evidence":[_evidence_to_dict(v) for _,v in sorted(self._ledger.evidence.items())],
              "actions":[_action_to_dict(v) for v in self._ledger.actions],
              "consumed_authorizations":[self._consumed_receipts[k] for k in sorted(self._consumed_receipts)]}
