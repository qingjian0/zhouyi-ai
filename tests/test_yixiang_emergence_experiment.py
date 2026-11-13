import unittest

from prototype.yixiang_emergence_experiment import (
    EmergenceExperimentAudit, EmergenceProtocol, ExperimentDecision,
    ExperimentalMeasurement, audit_emergence_experiment,
)


def protocol(**overrides):
    values = dict(
        experiment_id="exp-1",
        claim_id="em-1",
        metric_name="stability_score",
        expected_direction="higher",
        minimum_effect=2.0,
        minimum_independent_units=2,
        member_ids=("structure", "function"),
        necessary_member_ids=("structure", "function"),
        control_ids=("external_driver",),
        in_scope_signature="task-A|range-1",
        preregistration_ref="registry:protocol-1",
        registered_before_data=True,
    )
    values.update(overrides)
    return EmergenceProtocol(**values)


def measurements(**overrides):
    rows = []
    arms = {
        "member_baseline": (1.0, 1.2, "task-A|range-1"),
        "intact_composite": (8.0, 8.2, "task-A|range-1"),
        "bridge_removed": (2.0, 2.2, "task-A|range-1"),
        "member_removed:structure": (2.0, 2.1, "task-A|range-1"),
        "member_removed:function": (2.1, 2.2, "task-A|range-1"),
        "control:external_driver": (1.0, 1.1, "task-A|range-1"),
        "context_shift": (3.0, 3.2, "task-B|range-2"),
    }
    arms.update(overrides)
    index = 0
    for arm, (first, second, scope) in arms.items():
        for unit, outcome in (("unit-1", first), ("unit-2", second)):
            index += 1
            rows.append(ExperimentalMeasurement(
                f"m-{index}", "exp-1", arm, outcome, unit,
                f"evidence:{index}", scope,
            ))
    return tuple(rows)


class EmergenceExperimentTests(unittest.TestCase):
    def test_complete_preregistered_experiment_only_enters_review(self):
        result = audit_emergence_experiment(protocol(), measurements())
        self.assertEqual(result.decision, ExperimentDecision.HUMAN_REVIEW)
        self.assertEqual(len(result.contrasts), 5)
        self.assertEqual(result.scope_shift_mean, 3.1)
        self.assertEqual(result.interpretation_ceiling, "descriptive_preregistered_contrast_only")
        self.assertIn("not_causal_identification", result.non_claims)

    def test_missing_bridge_ablation_blocks(self):
        rows = tuple(row for row in measurements() if row.arm != "bridge_removed")
        result = audit_emergence_experiment(protocol(), rows)
        self.assertEqual(result.decision, ExperimentDecision.BLOCKED)
        self.assertIn("REQUIRED_EXPERIMENT_ARMS_MISSING", result.reason_codes)

    def test_missing_necessary_member_ablation_blocks(self):
        rows = tuple(row for row in measurements() if row.arm != "member_removed:function")
        result = audit_emergence_experiment(protocol(), rows)
        self.assertIn("REQUIRED_EXPERIMENT_ARMS_MISSING", result.reason_codes)

    def test_bridge_ablation_failure_blocks(self):
        rows = measurements(bridge_removed=(7.5, 7.6, "task-A|range-1"))
        result = audit_emergence_experiment(protocol(), rows)
        self.assertIn(
            "PREREGISTERED_CONTRAST_FAILED:composite_vs_bridge_removed",
            result.reason_codes,
        )

    def test_member_ablation_failure_blocks(self):
        rows = measurements(**{"member_removed:structure": (7.5, 7.6, "task-A|range-1")})
        result = audit_emergence_experiment(protocol(), rows)
        self.assertIn(
            "PREREGISTERED_CONTRAST_FAILED:composite_vs_member_removed:structure",
            result.reason_codes,
        )

    def test_control_that_matches_composite_blocks_claim(self):
        rows = measurements(**{"control:external_driver": (7.8, 7.9, "task-A|range-1")})
        result = audit_emergence_experiment(protocol(), rows)
        self.assertIn(
            "PREREGISTERED_CONTRAST_FAILED:composite_vs_control:external_driver",
            result.reason_codes,
        )

    def test_context_shift_must_change_scope_signature(self):
        rows = measurements(context_shift=(3.0, 3.2, "task-A|range-1"))
        result = audit_emergence_experiment(protocol(), rows)
        self.assertIn("CONTEXT_SHIFT_DID_NOT_CHANGE_SCOPE_SIGNATURE", result.reason_codes)

    def test_every_arm_requires_minimum_independent_units(self):
        rows = tuple(row for row in measurements() if not (
            row.arm == "intact_composite" and row.independent_unit_id == "unit-2"
        ))
        result = audit_emergence_experiment(protocol(), rows)
        self.assertIn(
            "INSUFFICIENT_INDEPENDENT_UNITS:intact_composite",
            result.reason_codes,
        )

    def test_duplicate_evidence_reference_blocks_by_validation(self):
        rows = list(measurements())
        rows[1] = ExperimentalMeasurement(
            rows[1].measurement_id, rows[1].experiment_id, rows[1].arm,
            rows[1].outcome, rows[1].independent_unit_id,
            rows[0].evidence_ref, rows[1].scope_signature,
        )
        with self.assertRaisesRegex(ValueError, "evidence_ref values must be unique"):
            audit_emergence_experiment(protocol(), tuple(rows))

    def test_unconfirmed_preregistration_blocks(self):
        result = audit_emergence_experiment(
            protocol(registered_before_data=False), measurements()
        )
        self.assertIn("PREREGISTRATION_NOT_CONFIRMED_BEFORE_DATA", result.reason_codes)

    def test_low_direction_is_supported(self):
        rows = measurements(
            member_baseline=(9.0, 9.2, "task-A|range-1"),
            intact_composite=(2.0, 2.2, "task-A|range-1"),
            bridge_removed=(8.0, 8.2, "task-A|range-1"),
            **{
                "member_removed:structure": (8.0, 8.1, "task-A|range-1"),
                "member_removed:function": (8.1, 8.2, "task-A|range-1"),
                "control:external_driver": (9.0, 9.1, "task-A|range-1"),
            },
        )
        result = audit_emergence_experiment(
            protocol(expected_direction="lower"), rows
        )
        self.assertEqual(result.decision, ExperimentDecision.HUMAN_REVIEW)

    def test_non_finite_outcome_is_rejected(self):
        rows = list(measurements())
        rows[0] = ExperimentalMeasurement(
            rows[0].measurement_id, rows[0].experiment_id, rows[0].arm,
            float("nan"), rows[0].independent_unit_id,
            rows[0].evidence_ref, rows[0].scope_signature,
        )
        with self.assertRaisesRegex(ValueError, "finite number"):
            audit_emergence_experiment(protocol(), tuple(rows))


if __name__ == "__main__":
    unittest.main()
