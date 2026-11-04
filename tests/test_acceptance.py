#!/usr/bin/env python3
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from run_acceptance import parse_json, run_suite, validate_config
EXE=None


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix="acceptance path ")
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.config=json.loads((ROOT/"configs/acceptance_serial.json").read_text())
        self.config["cases"]=[next(c for c in self.config["cases"] if c["name"]=="mixed_k5")]
        self.config_path=self.root/"config.json"

    def run_config(self,output="output"):
        self.config_path.write_text(json.dumps(self.config))
        return run_suite(EXE,self.config_path,self.root/output)

    def inject(self,mode):
        self.config["launch"]["prefix"]=[sys.executable,str(ROOT/"tests/fault_injection_launcher.py")]
        self.config["launch"]["env"]={"ACCEPTANCE_TEST_FAULT":mode}

    def test_full_serial_suite(self):
        self.config=json.loads((ROOT/"configs/acceptance_serial.json").read_text())
        summary=self.run_config()
        self.assertEqual(summary["status"],"PASS",summary)
        self.assertEqual(summary["cases"],14)

    def test_faults_and_logs(self):
        for mode in ("wrong_exit","bad_json","missing_file","transpose","bad_metadata","bad_residual","bad_iterations","extra_stdout"):
            with self.subTest(mode=mode):
                self.inject(mode)
                result=self.run_config(mode)
                self.assertEqual(result["status"],"FAIL",mode)
                for filename in ("stdout.log","stderr.log","command.json","verdict.json"):
                    self.assertTrue((self.root/mode/"mixed_k5"/filename).exists())
                self.assertIn("error",result["results"][0])

    def test_timeout(self):
        self.config["timeout_seconds"]=0.2
        self.inject("timeout")
        result=self.run_config()
        self.assertIn("timeout",result["results"][0]["error"])

    def test_missing_launcher(self):
        self.config["launch"]["prefix"]=[str(self.root/"not-present")]
        self.assertIn("launch_error",self.run_config()["results"][0]["error"])

    def test_launcher_and_environment(self):
        self.inject("environment")
        self.config["launch"]["env"].update(TEST_MARKER="present",OMP_NUM_THREADS="1")
        self.assertEqual(self.run_config()["status"],"PASS")

    def test_continues_after_failure(self):
        second=copy.deepcopy(self.config["cases"][0])
        second.update(name="after_failure",n=3)
        self.config["cases"].append(second)
        self.inject("bad_json")
        self.assertEqual([r["status"] for r in self.run_config()["results"]],["FAIL","PASS"])

    def test_stale_output_refused(self):
        (self.root/"output").mkdir()
        marker=self.root/"output/summary.json"
        marker.write_text('{"status":"PASS"}')
        with self.assertRaisesRegex(ValueError,"already exists"):
            self.run_config()
        self.assertEqual(marker.read_text(),'{"status":"PASS"}')

    def test_invalid_config(self):
        for change in (lambda c:c.update(cases=[]),lambda c:c.update(timeout_seconds=-1),
                       lambda c:c.update(timeout_seconds=float("nan")),
                       lambda c:c["cases"].append(dict(c["cases"][0])),
                       lambda c:c["cases"][0].update(n=True),
                       lambda c:c["cases"][0].update(n=256),
                       lambda c:c["cases"][0].update(name="../escape"),
                       lambda c:c["launch"].update(extra_args=["--solution=stale.csv"]),
                       lambda c:c["launch"].update(env={"OMP_NUM_THREADS":"4"}),
                       lambda c:c.update(unrecognized=True)):
            config=copy.deepcopy(self.config)
            change(config)
            with self.assertRaises(ValueError):
                validate_config(config)
        for text in ('{"x":1,"x":2}','{"x":NaN}'):
            with self.assertRaises(ValueError):
                parse_json(text)

    def test_reported_resources_must_match(self):
        for key in ("expected_ranks","expected_threads"):
            self.config["launch"][key]=2
            result=self.run_config(key)
            self.assertEqual(result["status"],"FAIL")
            self.assertIn("metadata mismatch",result["results"][0]["error"])
            self.config["launch"][key]=1

    def test_cli(self):
        self.config_path.write_text(json.dumps(self.config))
        command=[sys.executable,str(ROOT/"scripts/run_acceptance.py"),"--exe",str(EXE),
                 "--config",str(self.config_path),"--output",str(self.root/"output")]
        proc=subprocess.run(command,text=True,capture_output=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"],"PASS")
        proc=subprocess.run(command,text=True,capture_output=True)
        self.assertEqual(proc.returncode,2)
        self.assertEqual(json.loads(proc.stderr)["status"],"ERROR")
        self.inject("transpose")
        self.config_path.write_text(json.dumps(self.config))
        command[-1]=str(self.root/"failure")
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,1)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--exe",type=Path,required=True)
    args,remaining=parser.parse_known_args()
    EXE=args.exe.resolve()
    unittest.main(argv=[sys.argv[0],*remaining],verbosity=2)
