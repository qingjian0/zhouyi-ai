import unittest

from prototype.e12a7_multiworld import (
    collect, identify, make_worlds, run_benchmark, transfer,
)


class E12A7MultiworldTests(unittest.TestCase):
    def setUp(self):
        self.worlds = {world.name: world for world in make_worlds()}

    def test_all_declared_mechanisms_are_identifiable_with_interventions(self):
        for world in self.worlds.values():
            result = identify(collect(world, interventions=True))
            self.assertEqual(result["status"], "identified", (world.name, result))

    def test_observationally_equivalent_direct_and_confounder_abstain(self):
        direct = collect(self.worlds["direct_world"], interventions=False)
        confounded = collect(self.worlds["confounded_world"], interventions=False)
        self.assertEqual(
            [(r.intervention, r.x, r.context, r.time, r.y) for r in direct],
            [(r.intervention, r.x, r.context, r.time, r.y) for r in confounded],
        )
        result = transfer(direct, confounded)
        self.assertEqual(result["decision"], "abstain")
        self.assertEqual(result["reason"], "source_or_target_not_identified")

    def test_interventions_separate_direct_from_confounding(self):
        direct = identify(collect(self.worlds["direct_world"]))
        confounded = identify(collect(self.worlds["confounded_world"]))
        self.assertEqual(direct["candidates"], ["direct"])
        self.assertEqual(confounded["candidates"], ["confounded"])

    def test_surface_similarity_does_not_force_transfer(self):
        result = transfer(
            collect(self.worlds["direct_world"]),
            collect(self.worlds["inverse_world"]),
        )
        self.assertEqual(result["decision"], "reject_transfer")

    def test_context_and_delayed_switch_are_distinct_mechanisms(self):
        context = identify(collect(self.worlds["context_world"]))
        switch = identify(collect(self.worlds["switch_world"]))
        self.assertEqual(context["candidates"], ["context_gate"])
        self.assertEqual(switch["candidates"], ["delayed_switch"])

    def test_noise_and_missingness_are_tolerated_within_error_budget(self):
        rows = collect(self.worlds["noisy_missing_world"])
        self.assertGreater(sum(row.noisy and row.y is not None for row in rows), 0)
        result = identify(rows)
        self.assertEqual(result["status"], "identified")
        self.assertEqual(result["candidates"], ["direct"])

    def test_benchmark_reports_surface_tag_collision(self):
        result = run_benchmark()
        self.assertEqual(result["world_count"], 7)
        self.assertEqual(result["surface_tag_vocabulary_size"], 1)
        self.assertEqual(result["transfer_cases"]["direct_to_direct"]["decision"], "transfer")
        self.assertEqual(result["transfer_cases"]["direct_to_inverse"]["decision"], "reject_transfer")


if __name__ == "__main__":
    unittest.main()
