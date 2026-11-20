import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from soc_itg.flow import plan_flow, flow_command
from soc_itg.workspace import load_repo

INFO = """name: repo_a
vlnv: acme.com:L:a:1.0
syn:
  - top: core_top
    sdc: ${SDC_DIR}/core.sdc
    upf: ${UPF_DIR}/core.upf
cdc_check:
  - top: core_top
    sdc: ${SDC_DIR}/core.sdc
    waive: ${CDC_DIR}/cdc.waive
  - top: dma_top
    sdc: ${SDC_DIR}/dma.sdc
    waive: ${CDC_DIR}/dma.waive
"""


class FlowTest(unittest.TestCase):
    def test_plan(self):
        with tempfile.TemporaryDirectory() as td:
            repo_path = Path(td) / "repo_a"
            repo_path.mkdir()
            (repo_path / "repo_a_info.yaml").write_text(INFO, encoding="utf-8")
            repo = load_repo(repo_path)
            plans = plan_flow(repo, "cdc_check")
            self.assertEqual(len(plans), 2)
            self.assertEqual(plans[0]["top"], "core_top")
            only_core = plan_flow(repo, "cdc_check", tops={"core_top"})
            self.assertEqual(len(only_core), 1)
            cmd = flow_command("syn", plan_flow(repo, "syn")[0])
            self.assertIn("flow syn", cmd)
            self.assertIn("--top core_top", cmd)


if __name__ == "__main__":
    unittest.main()
