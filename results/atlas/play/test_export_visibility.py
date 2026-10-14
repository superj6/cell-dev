"""No-simulation checks of explicit browser ABI export and unchanged organism payloads."""
import unittest

import numpy as np
from export_bodies import body_record, world_dict

from src.life import probe, spec


class BrowserExportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.org, cls.preset = probe.hand("router@ring4")

    def test_default_export_retains_abi3_contract(self):
        world = self.org.world(self.preset)
        record = body_record(self.org, world)
        self.assertEqual(record["abi"], 3)
        self.assertEqual(list(record["world"]), list(spec.V3.WORLD_KEYS))
        self.assertEqual(len(record["world_vec"]), 66)
        self.assertNotIn("visibility_mode", record["world"])

    def test_visibility_cannot_be_silently_dropped(self):
        world = self.org.world("catch_speck_flash5_dim25_l4")
        with self.assertRaises(NotImplementedError):
            world_dict(world)
        with self.assertRaises(NotImplementedError):
            body_record(self.org, world)

    def test_abi4_exports_all_new_fields_and_unchanged_program(self):
        world = self.org.world("catch_speck_blink20_20_l4")
        record = body_record(self.org, world, abi=4)
        self.assertEqual(record["abi"], 4)
        self.assertEqual(list(record["world"]), list(spec.V4.WORLD_KEYS))
        self.assertEqual(record["world_vec"][-4:], [2, 20, 20, 0])
        self.assertEqual(len(record["world_vec"]), 70)
        np.testing.assert_array_equal(record["program"], self.org.program)
        self.assertEqual(record["cells"], [list(c) for c in self.org.cells])

    def test_abi_object_and_integer_export_identically(self):
        world = self.org.world("catch_speck_flash5_dim25_l4")
        self.assertEqual(body_record(self.org, world, abi=4), body_record(self.org, world, abi=spec.V4))

    def test_unsupported_export_abi_rejected(self):
        with self.assertRaises(ValueError):
            world_dict(self.org.world(self.preset), abi=2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
