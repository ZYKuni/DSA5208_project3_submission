#!/usr/bin/env python3
"""Validate complete zero-Dirichlet CSV grids and compare every coordinate."""
import argparse
import csv
import json
import math
from pathlib import Path
import re


class GridError(ValueError):
    pass


def validate_tolerances(atol, rtol, boundary_atol):
    for name, value in (("atol", atol), ("rtol", rtol), ("boundary_atol", boundary_atol)):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise GridError(name + " must be finite and nonnegative")


def load_grid(path, n, boundary_atol=0.0):
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise GridError("n must be a positive integer")
    validate_tolerances(0.0, 0.0, boundary_atol)
    field = {}
    with Path(path).open(newline="", encoding="utf-8") as stream:
        reader = csv.reader(stream, strict=True)
        if next(reader, None) != ["global_i", "global_j", "u"]:
            raise GridError("header must be exactly global_i,global_j,u")
        for line, row in enumerate(reader, 2):
            if len(row) != 3:
                raise GridError("line %d: expected three CSV columns" % line)
            if not all(re.fullmatch(r"[0-9]+", value.strip()) for value in row[:2]):
                raise GridError("line %d: coordinates must be nonnegative integers" % line)
            i, j = (int(value) for value in row[:2])
            if not (0 <= i <= n+1 and 0 <= j <= n+1):
                raise GridError("line %d: coordinate outside the expected grid" % line)
            if (i, j) in field:
                raise GridError("line %d: duplicate coordinate (%d,%d)" % (line, i, j))
            try:
                value = float(row[2])
            except ValueError as exc:
                raise GridError("line %d: invalid field value" % line) from exc
            if not math.isfinite(value):
                raise GridError("line %d: field value is not finite" % line)
            if (i in (0, n+1) or j in (0, n+1)) and abs(value) > boundary_atol:
                raise GridError("line %d: nonzero physical boundary at (%d,%d)" % (line, i, j))
            field[i, j] = value
    expected = (n+2)**2
    # Uniqueness plus in-range coordinates and the count proves completeness.
    if len(field) != expected:
        raise GridError("incomplete grid: expected %d points, got %d" % (expected, len(field)))
    return field


def compare_fields(reference, candidate, atol=1e-10, rtol=1e-10):
    validate_tolerances(atol, rtol, 0.0)
    if not reference or reference.keys() != candidate.keys():
        raise GridError("coordinate sets differ or are empty")
    max_error = error_l2 = reference_l2 = 0.0
    worst = None
    mismatches = 0
    for point in sorted(reference):
        a, b = reference[point], candidate[point]
        difference = abs(b-a)
        threshold = atol + rtol * abs(a)
        if not all(math.isfinite(v) for v in (a, b, difference, threshold)):
            raise GridError("nonfinite comparison value or arithmetic overflow")
        error_l2 = math.hypot(error_l2, difference)
        reference_l2 = math.hypot(reference_l2, a)
        if worst is None or difference > max_error:
            worst, max_error = point, difference
        if difference > threshold:
            mismatches += 1
    if not math.isfinite(error_l2) or not math.isfinite(reference_l2):
        raise GridError("L2 norm overflow")
    relative = error_l2/reference_l2 if reference_l2 else None
    if relative is not None and not math.isfinite(relative):
        raise GridError("relative L2 overflow")
    return {"status": "PASS" if mismatches == 0 else "FAIL", "points": len(reference),
            "mismatched_points": mismatches, "max_abs_error": max_error,
            "worst_coordinate": list(worst), "absolute_l2_error": error_l2,
            "reference_l2": reference_l2, "relative_l2_error": relative,
            "l2_error_kind": "relative" if reference_l2 else "absolute_zero_reference",
            "atol": atol, "rtol": rtol,
            "pass_rule": "all points satisfy abs(candidate-reference) <= atol + rtol*abs(reference)"}


def compare_files(reference, candidate, n, atol=1e-10, rtol=1e-10, boundary_atol=0.0):
    report = {"schema_version": 1, "reference": str(reference), "candidate": str(candidate),
              "n": n if type(n) is int else None,
              "boundary_atol": boundary_atol if type(boundary_atol) in (int,float) and math.isfinite(boundary_atol) else None}
    try:
        validate_tolerances(atol, rtol, boundary_atol)
        fields = []
        for role, path in (("reference", reference), ("candidate", candidate)):
            try:
                fields.append(load_grid(path, n, boundary_atol))
            except (OSError, ValueError, csv.Error) as exc:
                raise GridError(role + ": " + str(exc)) from exc
        report.update(compare_fields(*fields, atol=atol, rtol=rtol))
    except (OSError, ValueError, csv.Error) as exc:
        report.update(status="ERROR", error=str(exc))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--n", type=int, required=True)
    parser.add_argument("--atol", type=float, default=1e-10)
    parser.add_argument("--rtol", type=float, default=1e-10)
    parser.add_argument("--boundary-atol", type=float, default=0.0)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.report and args.report.resolve() in (args.reference.resolve(), args.candidate.resolve()):
        parser.error("report must not overwrite an input CSV")
    report = compare_files(args.reference, args.candidate, args.n, args.atol, args.rtol, args.boundary_atol)
    text = json.dumps(report, indent=2, allow_nan=False) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text)
    print(text, end="")
    return {"PASS": 0, "FAIL": 1, "ERROR": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
