#!/usr/bin/env python3
"""Analytic metric checks and failure exclusion; synthetic data stay in tempdirs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from run_experiments import check_config, build_command
from summarize_results import summarize

class Metrics(unittest.TestCase):
    def fixture(self,kind,base_cores,other_cores,base_time,other_time):
        cases=[{"label":"base","variant":"mpi","n":8,"ranks":base_cores,"threads":1},
               {"label":"other","variant":"mpi","n":8,"ranks":other_cores,"threads":1}]
        config={"schema_version":1,"scope":"local-container","repeats":3,"warmups":1,"launcher":[],
            "studies":[{"id":"test","kind":kind,"baseline":"base","iterations":10,"cases":cases}]}
        runs=[{"study":"test","label":case["label"],"warmup":False,"status":"PASS",
               "result":{"solve_seconds_max":time}} for case,time in zip(cases,(base_time,other_time)) for _ in range(3)]
        return config,runs
    def evaluate(self,c,r):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d);(path/"config.json").write_text(json.dumps(c));(path/"runs.json").write_text(json.dumps(r))
            return summarize(path)
    def test_strong_serial_baseline(self):
        c,r=self.fixture("strong",1,4,8,2);row=self.evaluate(c,r)[1]
        self.assertEqual(row["speedup"],4);self.assertEqual(row["efficiency"],1)
    def test_relative_baseline(self):
        c,r=self.fixture("ratio",4,4,8,4);row=self.evaluate(c,r)[1]
        self.assertEqual(row["efficiency"],2)
    def test_weak_does_not_divide_by_cores(self):
        c,r=self.fixture("weak",1,4,3,6);row=self.evaluate(c,r)[1]
        self.assertEqual(row["efficiency"],.5);self.assertIsNone(row["speedup"])
    def test_failed_and_missing_repeats_have_no_metrics(self):
        c,r=self.fixture("strong",1,4,8,2)
        r[-1]["status"]="FAIL"
        row=self.evaluate(c,r)[1];self.assertEqual(row["status"],"INCOMPLETE");self.assertIsNone(row["efficiency"])
        row=self.evaluate(c,r[:-1])[1];self.assertIsNone(row["median_seconds"])
    def test_invalid_fairness_rejected(self):
        c,_=self.fixture("strong",1,4,8,2);c["studies"][0]["cases"][1]["n"]=9
        with self.assertRaises(ValueError):check_config(c)
        c,_=self.fixture("ratio",1,4,8,2)
        with self.assertRaises(ValueError):check_config(c)
    def test_b_mpi_and_hybrid_launches(self):
        c,_=self.fixture("strong",1,4,8,2)
        c["launcher"]=["mpiexec","-n","{ranks}"]
        study=c["studies"][0];case=study["cases"][1]
        command=build_command(c,study,case,Path("/bin"))
        self.assertEqual(command[:4],["mpiexec","-n","4","/bin/poisson_mpi"])
        self.assertNotIn("--kernel",command)
        case.update(variant="mpi_openmp",ranks=2,threads=2,communication="overlap")
        command=build_command(c,study,case,Path("/bin"))
        self.assertIn("/bin/poisson_hybrid",command)
        self.assertEqual(command[command.index("--communication")+1],"overlap")
        self.assertEqual(command[command.index("--kernel")+1],"openmp")
        self.assertEqual(command.count("-n"),1)

if __name__=="__main__":unittest.main()
