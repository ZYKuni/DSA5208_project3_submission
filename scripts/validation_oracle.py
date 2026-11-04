"""Independent small-grid modal oracle; never calls or loads the C++ solver."""
import csv
import math
from pathlib import Path

PROBLEMS = ("continuous-sine", "discrete-sine", "zero", "discrete-mixed")


def modes(problem):
    if problem == "zero":
        return []
    if problem == "discrete-mixed":
        return [(1, 2, 1.0), (2, 3, 0.35)]  # (x frequency, y frequency, amplitude)
    if problem in ("continuous-sine", "discrete-sine"):
        return [(1, 1, 1.0)]
    raise ValueError("unsupported oracle problem: " + problem)


def eigenvalue(n, px, py):
    h = 1.0/(n+1)
    return 4*(math.sin(px*math.pi*h/2)**2 + math.sin(py*math.pi*h/2)**2)/(h*h)


def field_at_step(n, problem, iterations):
    result = {}
    h = 1.0/(n+1)
    for i in range(n+2):
        for j in range(n+2):
            value = 0.0
            if 0 < i < n+1 and 0 < j < n+1:
                for px, py, amplitude in modes(problem):
                    rho = (math.cos(px*math.pi*h) + math.cos(py*math.pi*h))/2
                    ratio = 2*math.pi**2/eigenvalue(n, px, py) if problem == "continuous-sine" else 1.0
                    value += amplitude*ratio*(1-rho**iterations)*math.sin(px*math.pi*j*h)*math.sin(py*math.pi*i*h)
            result[i, j] = value
    return result


def exact_field(n, problem):
    result = {}
    for i in range(n+2):
        for j in range(n+2):
            result[i, j] = (sum(a*math.sin(px*math.pi*j/(n+1))*math.sin(py*math.pi*i/(n+1))
                                for px, py, a in modes(problem))
                            if 0 < i < n+1 and 0 < j < n+1 else 0.0)
    return result


def rhs_field(n, problem):
    # For discrete problems, apply an independently assembled mathematical
    # operator to the exact field rather than copying C++ RHS eigenvalue code.
    exact = exact_field(n, problem)
    if problem == "continuous-sine":
        return {point: 2*math.pi**2*value for point, value in exact.items()}
    scale = (n+1)**2
    rhs = {point: 0.0 for point in exact}
    for i in range(1, n+1):
        for j in range(1, n+1):
            rhs[i, j] = scale*(4*exact[i,j]-exact[i-1,j]-exact[i+1,j]-exact[i,j-1]-exact[i,j+1])
    return rhs


def residual_metrics(field, n, problem):
    rhs = rhs_field(n, problem)
    scale = (n+1)**2
    residual = norm = 0.0
    for i in range(1, n+1):
        for j in range(1, n+1):
            au = scale*(4*field[i,j]-field[i-1,j]-field[i+1,j]-field[i,j-1]-field[i,j+1])
            residual = math.hypot(residual, rhs[i,j]-au)
            norm = math.hypot(norm, rhs[i,j])
    return {"absolute": residual, "rhs_l2": norm,
            "relative": residual/norm if norm else residual,
            "kind": "relative_l2" if norm else "absolute_l2"}


def dense_reference(n, problem, iterations):
    coords = [(i,j) for i in range(1,n+1) for j in range(1,n+1)]
    scale = (n+1)**2
    matrix = [[(4*scale if a == b else -scale if abs(i-k)+abs(j-ell) == 1 else 0)
               for b,(k,ell) in enumerate(coords)] for a,(i,j) in enumerate(coords)]
    rhs = rhs_field(n, problem)
    x = [0.0]*len(coords)
    for _ in range(iterations):
        x = [(rhs[coords[a]] - sum(matrix[a][b]*x[b] for b in range(len(x)) if a != b))/matrix[a][a]
             for a in range(len(x))]
    field = {(i,j):0.0 for i in range(n+2) for j in range(n+2)}
    field.update(zip(coords, x))
    return field


def write_grid(path, field):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow(["global_i", "global_j", "u"])
        for (i,j), value in sorted(field.items()):
            writer.writerow([i,j,format(value,".17g")])
