#!/usr/bin/env python3
import csv
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from compare_grids import compare_files
from validation_oracle import field_at_step, write_grid


class GridComparisonTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.reference=self.root/"reference.csv"
        self.candidate=self.root/"candidate.csv"
        self.field=field_at_step(7,"discrete-mixed",5)
        write_grid(self.reference,self.field)
        write_grid(self.candidate,self.field)

    def report(self, **kwargs):
        return compare_files(self.reference,self.candidate,7,**kwargs)

    def mutate(self, action):
        with self.candidate.open(newline="") as stream:
            rows=list(csv.reader(stream))
        action(rows)
        with self.candidate.open("w",newline="") as stream:
            csv.writer(stream,lineterminator="\n").writerows(rows)

    def test_equal_reordered(self):
        self.mutate(lambda rows: rows.__setitem__(slice(1,None),list(reversed(rows[1:]))))
        report=self.report()
        self.assertEqual(report["status"],"PASS")
        self.assertEqual(report["relative_l2_error"],0)
        self.assertEqual(report["points"],81)

    def test_metrics_and_tolerance(self):
        changed=dict(self.field)
        changed[2,3]+=1e-5
        write_grid(self.candidate,changed)
        report=self.report(atol=0,rtol=0)
        self.assertEqual(report["status"],"FAIL")
        self.assertEqual(report["mismatched_points"],1)
        self.assertEqual(report["worst_coordinate"],[2,3])
        self.assertAlmostEqual(report["max_abs_error"],1e-5,places=14)
        self.assertAlmostEqual(report["absolute_l2_error"],1e-5,places=14)
        self.assertAlmostEqual(report["relative_l2_error"],1e-5/math.sqrt(sum(x*x for x in self.field.values())),places=14)
        self.assertEqual(self.report(atol=2e-5,rtol=0)["status"],"PASS")

    def test_relative_tolerance(self):
        changed=dict(self.field)
        changed[2,3]*=1+5e-7
        write_grid(self.candidate,changed)
        self.assertEqual(self.report(atol=0,rtol=1e-6)["status"],"PASS")
        self.assertEqual(self.report(atol=0,rtol=1e-8)["status"],"FAIL")

    def test_missing_and_duplicate(self):
        self.mutate(lambda rows: rows.pop())
        self.assertIn("incomplete",self.report()["error"])
        write_grid(self.candidate,self.field)
        self.mutate(lambda rows: rows.__setitem__(-1,rows[-2]))
        self.assertIn("duplicate",self.report()["error"])

    def test_bad_coordinates(self):
        for value in ("-1","1.5","9","NaN"):
            with self.subTest(value=value):
                write_grid(self.candidate,self.field)
                self.mutate(lambda rows: rows[1].__setitem__(0,value))
                self.assertEqual(self.report()["status"],"ERROR")

    def test_nonfinite_values(self):
        for value in ("nan","inf","-inf","1e999","not-a-number",""):
            with self.subTest(value=value):
                write_grid(self.candidate,self.field)
                self.mutate(lambda rows: rows[11].__setitem__(2,value))
                self.assertEqual(self.report()["status"],"ERROR")

    def test_boundary(self):
        changed=dict(self.field)
        changed[0,3]=1e-12
        write_grid(self.candidate,changed)
        self.assertIn("physical boundary",self.report()["error"])
        self.assertEqual(self.report(boundary_atol=2e-12)["status"],"PASS")
        write_grid(self.reference,changed)
        self.assertIn("reference:",self.report()["error"])

    def test_bad_csv(self):
        for action in (lambda r:r[0].append("extra"),lambda r:r[2].append("extra"),
                       lambda r:r.insert(3,[]),lambda r:r[0].__setitem__(1,"global_i")):
            write_grid(self.candidate,self.field)
            self.mutate(action)
            self.assertEqual(self.report()["status"],"ERROR")

    def test_zero_reference(self):
        zero={point:0.0 for point in self.field}
        write_grid(self.reference,zero)
        write_grid(self.candidate,zero)
        report=self.report()
        self.assertEqual(report["status"],"PASS")
        self.assertIsNone(report["relative_l2_error"])
        self.assertEqual(report["l2_error_kind"],"absolute_zero_reference")
        zero[2,3]=1
        write_grid(self.candidate,zero)
        self.assertEqual(self.report()["status"],"FAIL")
        self.assertEqual(self.report()["absolute_l2_error"],1)

    def test_transpose_and_reflections(self):
        for transform in (lambda i,j:(j,i),lambda i,j:(8-i,j),lambda i,j:(i,8-j)):
            write_grid(self.candidate,{(i,j):self.field[transform(i,j)] for i,j in self.field})
            self.assertEqual(self.report()["status"],"FAIL")

    def test_invalid_options_and_missing_file(self):
        for options in ({"atol":-1},{"rtol":float("nan")},{"boundary_atol":float("inf")}):
            self.assertEqual(self.report(**options)["status"],"ERROR")
        self.assertEqual(compare_files(self.reference,self.candidate,0)["status"],"ERROR")
        self.candidate.unlink()
        self.assertEqual(self.report()["status"],"ERROR")

    def test_overflow(self):
        a,b=dict(self.field),dict(self.field)
        a[2,3],b[2,3]=1e308,-1e308
        write_grid(self.reference,a)
        write_grid(self.candidate,b)
        self.assertEqual(self.report()["status"],"ERROR")

    def test_cli_invalid_tolerance(self):
        tool=Path(__file__).resolve().parents[1]/"scripts/compare_grids.py"
        proc=subprocess.run([sys.executable,str(tool),"--reference",str(self.reference),
                             "--candidate",str(self.candidate),"--n","7","--boundary-atol","nan"],
                             text=True,capture_output=True)
        self.assertEqual(proc.returncode,2)
        self.assertEqual(json.loads(proc.stdout)["status"],"ERROR")

    def test_cli(self):
        tool=Path(__file__).resolve().parents[1]/"scripts/compare_grids.py"
        report=self.root/"report.json"
        command=[sys.executable,str(tool),"--reference",str(self.reference),"--candidate",str(self.candidate),"--n","7","--report",str(report)]
        proc=subprocess.run(command,text=True,capture_output=True)
        self.assertEqual(proc.returncode,0,proc.stderr)
        self.assertEqual(json.loads(proc.stdout),json.loads(report.read_text()))
        changed=dict(self.field)
        changed[2,3]+=1
        write_grid(self.candidate,changed)
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,1)
        self.candidate.unlink()
        self.assertEqual(subprocess.run(command,capture_output=True).returncode,2)


if __name__=="__main__":
    unittest.main(verbosity=2)
