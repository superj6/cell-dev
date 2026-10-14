"""Targeted read-only fault injection for the reused genetic/selection checks."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import unittest

module_spec = importlib.util.spec_from_file_location("U_final_genetics_audit", Path(__file__).with_name("audit.py"))
audit = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(audit)


class GeneticAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        audit.torch.set_num_threads(1)
        cls.L, cls.G = audit.load_helpers()
        from src.genome import Layout
        from src.life import spec
        cls.spec = spec
        cls.layout, cls.founder = Layout.load(audit.STUDY / "inputs/founder_s5_row32.json")
        folder = audit.STUDY / "runs/s53091"
        cls.lines = [json.loads(line) for line in (folder / "lineage.jsonl").read_bytes().splitlines()]
        cls.saved = audit.torch.load(io.BytesIO((folder / "checkpoint.pt").read_bytes()),
                                    map_location="cpu", weights_only=True)
        cls.state = cls.saved["state"]

    def replay(self, lines=None, state=None):
        return self.G.replay_genetics(self.lines if lines is None else lines,
            self.state if state is None else state, self.layout, self.founder, structural=False)

    def test_uncorrupted_recorded_replay(self):
        self.assertTrue(self.replay()["raw_population_replay_bitwise"])

    def test_changed_raw_final_genotype_rejected(self):
        state = copy.deepcopy(self.state)
        state["population"][0, 0] += 1.0
        with self.assertRaisesRegex(ValueError, "raw final population"):
            self.replay(state=state)

    def test_changed_final_origin_rejected(self):
        state = copy.deepcopy(self.state)
        state["origins"][0, 0] += 1
        with self.assertRaisesRegex(ValueError, "final origins"):
            self.replay(state=state)

    def test_out_of_range_crossover_mask_rejected(self):
        lines = copy.deepcopy(self.lines)
        lines[1]["children"][0]["mask"] = 1 << self.layout.n_units
        with self.assertRaisesRegex(ValueError, "invalid crossover unit mask"):
            self.replay(lines=lines)

    def test_nonexistent_parent_rejected(self):
        lines = copy.deepcopy(self.lines)
        lines[1]["children"][0]["pa"] = -1
        with self.assertRaisesRegex(ValueError, "offspring parent missing"):
            self.replay(lines=lines)

    def test_structural_operator_rejected(self):
        lines = copy.deepcopy(self.lines)
        lines[1]["children"][0]["ops"]["dup"] = [0, 8]
        with self.assertRaisesRegex(ValueError, "structural mutation"):
            self.replay(lines=lines)

    def test_changed_selection_fitness_rejected(self):
        lines, curves = audit.selection_view(self.lines, self.state["curves"], 1024)
        lines[1]["fitness"][0] += 1.0
        with self.assertRaisesRegex(ValueError, "seven-life pooled scores"):
            self.L.audit_lineage(lines, curves, self.state, 53091, self.spec)

    def test_conflicting_recorded_duration_rejected(self):
        lines = copy.deepcopy(self.lines)
        lines[1]["T"] = 512
        with self.assertRaisesRegex(ValueError, "optional recorded duration"):
            audit.selection_view(lines, self.state["curves"], 1024)


if __name__ == "__main__":
    unittest.main(verbosity=2)
