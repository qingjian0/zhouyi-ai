import unittest
from prototype.e12a7_orthogonal_lifecycle import CandidateVersion, EpistemicStatus, OrthogonalLifecycleLedger, ScopeStatus
from prototype.e12a11_active_measurement_evidence import BudgetedMeasurementExecutor, MeasurementRequest, MeasurementSigner
from prototype.e12a13_drift_mismatch_diagnostics import DriftDiagnosis, DriftMismatchMonitor

CANDIDATE, SCOPE, CONTROL = "primitive:shape@1", "world-A", "control-known-v1"
def request(i, target, digest="scope-d"):
    return MeasurementRequest(f"req-{i}", CANDIDATE, SCOPE, digest, "probe-v1", target, "params-v1", 1.0, 1.0)

class DriftMismatchTests(unittest.TestCase):
    def setUp(self):
        self.signer = MeasurementSigner.generate("measurement-service", "key-1")
        self.ledger = OrthogonalLifecycleLedger()
        self.ledger.register(CandidateVersion("primitive:shape", 1, "shape relation", "dsl-v1"))
        self.monitor = DriftMismatchMonitor(candidate_ref=CANDIDATE, scope_id=SCOPE,
            scope_digest="scope-d", protocol_id="probe-v1",
            candidate_reference={"yes": 0.8, "no": 0.2},
            control_references={CONTROL: {"ok": 0.8, "bad": 0.2}},
            public_key_bytes=self.signer.public_key_bytes(), executor_id="measurement-service",
            key_id="key-1", ledger=self.ledger, min_samples=4, window_size=20, tv_threshold=0.25)

    def emit(self, streams):
        i = 0
        ex = BudgetedMeasurementExecutor(self.signer,
            {"probe-v1": lambda target, params: ("yes", 0.25)},
            allowed_candidate_scopes={(CANDIDATE, SCOPE)}, budget=100)
        for target, outcomes in streams.items():
            for outcome in outcomes:
                i += 1
                ex.protocols["probe-v1"] = lambda t, p, value=outcome: (value, 0.25)
                self.monitor.ingest(ex.execute(request(i, target)))
        return self.monitor.assess()

    def test_stable_controls_and_targets(self):
        result = self.emit({CONTROL:["ok","ok","ok","bad"], "target-a":["yes","yes","yes","no"]})
        self.assertEqual(result.diagnosis, DriftDiagnosis.STABLE)
        self.assertEqual(self.ledger.snapshot("primitive:shape",1,SCOPE)["scope_status"], ScopeStatus.UNTESTED.value)

    def test_control_drift_marks_shift_not_candidate_refutation(self):
        result = self.emit({CONTROL:["bad"]*4, "target-a":["yes"]*4})
        state = self.ledger.snapshot("primitive:shape",1,SCOPE)
        self.assertEqual(result.diagnosis, DriftDiagnosis.CONTROL_SHIFT)
        self.assertEqual(state["scope_status"], ScopeStatus.SHIFT_SUSPECTED.value)
        self.assertEqual(state["epistemic_status"], EpistemicStatus.UNKNOWN.value)

    def test_target_mismatch_is_not_refutation(self):
        result = self.emit({CONTROL:["ok"]*4, "target-a":["no"]*4})
        state = self.ledger.snapshot("primitive:shape",1,SCOPE)
        self.assertEqual(result.diagnosis, DriftDiagnosis.TARGET_MISMATCH)
        self.assertEqual(state["scope_status"], ScopeStatus.SHIFT_SUSPECTED.value)
        self.assertEqual(state["epistemic_status"], EpistemicStatus.UNKNOWN.value)

    def test_joint_shift(self):
        result = self.emit({CONTROL:["bad"]*4, "target-a":["no"]*4})
        self.assertEqual(result.diagnosis, DriftDiagnosis.JOINT_SHIFT)

    def test_insufficient_data_does_not_claim_stability(self):
        self.emit({CONTROL:["ok","ok"], "target-a":["yes","yes"]})
        self.assertEqual(self.monitor.assess().diagnosis, DriftDiagnosis.INSUFFICIENT_DATA)

    def test_scope_digest_mismatch_rejected(self):
        ex = BudgetedMeasurementExecutor(self.signer, {"probe-v1":lambda t,p:("yes",0.2)},
            allowed_candidate_scopes={(CANDIDATE,SCOPE)}, budget=10)
        with self.assertRaises(ValueError):
            self.monitor.ingest(ex.execute(request(1,"target-a","wrong")))

    def test_incompatible_control_reference_models_rejected(self):
        with self.assertRaises(ValueError):
            DriftMismatchMonitor(candidate_ref=CANDIDATE, scope_id=SCOPE,
                scope_digest="scope-d", protocol_id="probe-v1",
                candidate_reference={"yes":0.8,"no":0.2},
                control_references={"c1":{"ok":0.8,"bad":0.2},
                                    "c2":{"ok":0.6,"bad":0.4}},
                public_key_bytes=self.signer.public_key_bytes(),
                executor_id="measurement-service", key_id="key-1",
                ledger=self.ledger, min_samples=4)

    def test_wrong_protocol_version_rejected(self):
        signer = MeasurementSigner("measurement-service", "key-1",
            __import__("cryptography.hazmat.primitives.asymmetric.ed25519", fromlist=["Ed25519PrivateKey"]).Ed25519PrivateKey.generate(),
            protocol_version="measurement-v2")
        ex = BudgetedMeasurementExecutor(signer, {"probe-v1":lambda t,p:("yes",0.2)},
            allowed_candidate_scopes={(CANDIDATE,SCOPE)}, budget=10)
        with self.assertRaises(ValueError):
            self.monitor.ingest(ex.execute(request(1,"target-a")))

    def test_control_unknown_outcome_rejected(self):
        ex = BudgetedMeasurementExecutor(self.signer, {"probe-v1":lambda t,p:("unknown",0.2)},
            allowed_candidate_scopes={(CANDIDATE,SCOPE)}, budget=10)
        with self.assertRaises(ValueError):
            self.monitor.ingest(ex.execute(request(1,CONTROL)))

if __name__ == "__main__":
    unittest.main()
