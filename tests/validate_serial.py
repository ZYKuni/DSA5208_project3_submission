#!/usr/bin/env python3
"""Independent analytic / dense-reference validation using only Python stdlib."""
import argparse
import csv
import json
import math
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validation_oracle import dense_reference as mixed_dense_reference, field_at_step


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def read_field(path, n):
    rows = list(csv.DictReader(path.open()))
    require(len(rows) == (n + 2) ** 2, "incomplete field")
    field = {(int(r['global_i']), int(r['global_j'])): float(r['u']) for r in rows}
    require(len(field) == len(rows), "duplicate grid points")
    require(set(field) == {(i, j) for i in range(n+2) for j in range(n+2)}, "wrong coordinates")
    require(all(math.isfinite(v) for v in field.values()), "nonfinite solution")
    for (i, j), v in field.items():
        if i in (0, n+1) or j in (0, n+1):
            require(v == 0, "physical boundary changed")
    return field


def dense_reference(n, steps):
    # Dense linear algebra oracle for tiny problems; does not call C++ kernels.
    h2 = 1.0 / (n+1)**2
    coords = [(i, j) for i in range(1, n+1) for j in range(1, n+1)]
    matrix = [[0.0] * (n*n) for _ in coords]
    rhs = []
    for row, (i, j) in enumerate(coords):
        rhs.append(2*math.pi**2 * math.sin(math.pi*i/(n+1)) * math.sin(math.pi*j/(n+1)))
        for col, (k, ell) in enumerate(coords):
            matrix[row][col] = 4/h2 if row == col else (-1/h2 if abs(i-k)+abs(j-ell) == 1 else 0)
    x = [0.0] * len(coords)
    for _ in range(steps):
        x = [(rhs[i] - sum(matrix[i][j]*x[j] for j in range(len(x)) if i != j)) / matrix[i][i]
             for i in range(len(x))]
    return dict(zip(coords, x))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    exe = str(args.exe.resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    evidence = []
    raw = []

    def run(label, n, *options, expected=0):
        field_path = args.output / (label + '.csv')
        command = [exe, '--n', str(n), *options, '--solution', str(field_path)]
        proc = subprocess.run(command, text=True, capture_output=True)
        raw.append({'case': label, 'command': command, 'exit_code': proc.returncode,
                    'stdout': proc.stdout, 'stderr': proc.stderr})
        require(proc.returncode == expected, label + ': unexpected exit: ' + proc.stderr)
        result = json.loads(proc.stdout)
        field = read_field(field_path, n)
        evidence.append({'case': label, 'n': n, 'iterations': result['actual_iterations'],
                         'relative_residual': result['final_relative_residual'],
                         'max_exact_error': result['exact_max_abs_error'], 'status': 'PASS'})
        return result, field

    for n in (1, 2, 3, 7):
        for steps in (0, 1, 2, 5):
            result, field = run('dense_n%d_k%d' % (n, steps), n, '--iterations', str(steps))
            oracle = dense_reference(n, steps)
            require(max(abs(field[p]-v) for p,v in oracle.items()) < 1e-12, 'dense oracle mismatch')
            require(result['actual_iterations'] == steps, 'fixed mode stopped early')
            require(result['timed_residual_checks'] == steps, 'default residual schedule')

    for steps in (1, 2, 5, 16):
        result, field = run('eigenmode_k%d' % steps, 7, '--iterations', str(steps), '--problem', 'discrete-sine')
        rho = math.cos(math.pi/8)
        for (i,j), value in field.items():
            target = (1-rho**steps)*math.sin(math.pi*i/8)*math.sin(math.pi*j/8)
            require(abs(value-target) < 2e-14, 'analytic iteration amplitude')
        require(abs(result['final_relative_residual']-rho**steps) < 2e-13, 'analytic residual decay')

    result, _ = run('fixed_check_interval', 7, '--iterations', '5', '--check-every', '3')
    require(result['timed_residual_checks'] == 2, 'must check at step 3 and final step 5')
    result, _ = run('fixed_no_early_stop', 1, '--iterations', '5', '--problem', 'discrete-sine')
    require(result['actual_iterations'] == 5 and result['converged'], 'fixed mode ignores early convergence')
    result, _ = run('zero_initial_converged', 7, '--mode', 'converge', '--problem', 'zero')
    require(result['actual_iterations'] == 0 and result['rhs_l2'] == 0, 'zero RHS initial stop')
    require(result['residual_kind'] == 'absolute_l2', 'zero denominator fallback')
    result, _ = run('zero_fixed', 7, '--iterations', '5', '--problem', 'zero')
    require(result['actual_iterations'] == 5 and result['final_absolute_residual'] == 0, 'zero fixed count')
    result, _ = run('nonconverged_exit', 7, '--mode', 'converge', '--iterations', '1', expected=2)
    require(result['stop_reason'] == 'max_iterations' and not result['converged'], 'nonconvergence status')
    result, _ = run('discrete_converged', 15, '--mode', 'converge', '--problem', 'discrete-sine',
                    '--iterations', '20000', '--tol', '1e-11', '--check-every', '7')
    require(result['final_relative_residual'] <= 1e-11, 'discrete tolerance')
    require(result['exact_max_abs_error'] < 2e-11, 'discrete known solution')
    require(result['actual_iterations'] % 7 == 0, 'convergence checking interval')

    # Independently assembled dense matrix and modal evolution.
    for n in (3, 7):
        for steps in (1, 2, 5):
            result, field = run('mixed_dense_n%d_k%d' % (n, steps), n,
                                '--problem', 'discrete-mixed', '--iterations', str(steps))
            oracle = mixed_dense_reference(n, 'discrete-mixed', steps)
            require(max(abs(field[p]-v) for p,v in oracle.items()) < 1e-12, 'mixed dense oracle mismatch')
            modal = field_at_step(n, 'discrete-mixed', steps)
            require(max(abs(field[p]-v) for p,v in modal.items()) < 1e-12, 'mixed modal mismatch')
    result, field = run('mixed_modal_k16', 7, '--problem', 'discrete-mixed', '--iterations', '16')
    modal = field_at_step(7, 'discrete-mixed', 16)
    require(max(abs(field[p]-v) for p,v in modal.items()) < 1e-12, 'mixed long modal mismatch')
    result, _ = run('mixed_converged', 15, '--mode', 'converge', '--problem', 'discrete-mixed',
                    '--iterations', '20000', '--tol', '1e-11', '--check-every', '7')
    require(result['exact_max_abs_error'] < 2e-11, 'mixed discrete exact solution')

    errors = []
    for n in (7, 15, 31):
        result, _ = run('refinement_n%d' % n, n, '--mode', 'converge',
                        '--iterations', '20000', '--tol', '1e-11', '--check-every', '5')
        require(result['final_relative_residual'] <= 1e-11, 'continuous convergence')
        errors.append(result['exact_max_abs_error'])
    ratios = [a/b for a,b in zip(errors, errors[1:])]
    require(all(3.9 < ratio < 4.1 for ratio in ratios), 'expected second-order refinement')

    bad_options = [ ['--n', '0'], ['--n', '-1'], ['--n', '2.5'], ['--n', str(2**64-1)],
                    ['--tol', 'nan'], ['--tol', 'inf'], ['--tol', '0'], ['--tol', '1e-5junk'],
                    ['--check-every', '0'], ['--mode', 'bad'], ['--problem', 'bad'],
                    ['--iterations', '-1'], ['--mode', 'converge', '--iterations', '0'],
                    ['--unknown', 'x'], ['--n'], ['--n', '2', '--problem', 'discrete-mixed'] ]
    for options in bad_options:
        proc = subprocess.run([exe, *options], text=True, capture_output=True)
        require(proc.returncode == 1 and not proc.stdout, 'invalid CLI accepted: ' + str(options))
        raw.append({'case': 'invalid_cli', 'options': options, 'exit_code': proc.returncode,
                    'stdout': proc.stdout, 'stderr': proc.stderr})
    with (args.output / 'validation.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(evidence[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(evidence)
    (args.output / 'runs.json').write_text(json.dumps(raw, indent=2) + '\n')
    summary = {'scope': 'local_serial_validation_only', 'numerical_cases': len(evidence),
               'invalid_cli_cases': len(bad_options), 'refinement_max_errors': errors,
               'refinement_ratios': ratios, 'status': 'PASS'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
