"""Offline checks for experimental statistics and paired design."""

import math
import unittest

import run


class HarnessTests(unittest.TestCase):
    def test_stable_weights(self):
        self.assertEqual(run.weights([-10000, -10000]), [0.5, 0.5])
        self.assertAlmostEqual(sum(run.weights([-10000, -10001])), 1)
        with self.assertRaises(ValueError):
            run.weights([math.nan])

    def test_prefixes_and_duplicates_are_token_based(self):
        self.assertEqual(run.token_issues([[1], [1, 2], [1], [3]]),
                         {"duplicates": [[0, 2]], "strict_prefixes": [[0, 1], [2, 1]]})

    def test_ordinal_and_interval(self):
        ordinal = run.summarize([0, 5, 10], [0.5, 0, 0.5], "ordinal")
        self.assertNotIn("interval", ordinal)
        self.assertEqual(ordinal["ordinal"]["modes"], [0, 10])
        self.assertEqual(ordinal["ordinal"]["median"], 0)
        self.assertEqual(ordinal["ordinal"]["quantiles"]["0.9"], 10)
        interval = run.summarize([0, 5, 10], [0.5, 0, 0.5], "interval")
        self.assertEqual(interval["interval"], {"expected_value": 5, "standard_deviation": 5})

    def test_distribution_distances(self):
        result = run.distances([0, 10], [1, 0], [0, 5, 10], [0, 0, 1])
        self.assertEqual(result, {"total_variation": 1, "wasserstein_1_numeric": 10})
        self.assertEqual(run.distances([0, 10], [0.5, 0.5], [0, 5, 10], [0.5, 0, 0.5])["total_variation"], 0)

    def test_equal_length_mean_changes_weights_not_mode(self):
        sums, means = run.weights([-2, -4]), run.weights([-1, -2])
        self.assertGreater(sums[0], means[0])
        self.assertGreater(means[0], means[1])

    def test_pairing(self):
        plan = run.build_plan()
        self.assertEqual(len(plan), 399)
        self.assertEqual(len(run.build_plan(True)), 279)
        self.assertEqual(len(run.build_plan(paraphrases=True)), 210)
        for spec in run.build_plan(paraphrases=True):
            self.assertEqual(spec["measurement"], "ordinal")
            self.assertTrue(spec["case"].startswith("paraphrase_"))
            self.assertFalse(any(spec["task"].endswith(d) for d in run.DESCRIPTIONS))
        for spec in plan:
            self.assertIn(spec["expected"], spec["values"])
            labels = run.labels_for(spec)
            self.assertEqual(len(labels), len(spec["values"]))
            self.assertEqual(len(set(labels)), len(labels))
            if spec["variant"] in ["numeric_ended", "numeric_space", "numeric_api_reverse", "numeric_raw"]:
                base = {**spec, "variant": "numeric"}
                self.assertEqual(run.messages_for(spec, labels), run.messages_for(base, run.labels_for(base)))
        signed = {"values": [-2, -1, 0, 1, 2], "variant": "fixed"}
        self.assertEqual(run.labels_for(signed), ["-02", "-01", "+00", "+01", "+02"])

    def test_correlation_undefined_for_equal_counts(self):
        self.assertIsNone(run.correlation([1, 1], [2, 3]))
        self.assertAlmostEqual(run.correlation([1, 2, 3], [3, 2, 1]), -1)


if __name__ == "__main__":
    unittest.main()
