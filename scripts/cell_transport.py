"""Isothermal two-parameter transport, Davidson et al. 2014, Eq. 1.

This is a reference-cell model, not a viability or freezing simulator.
State: w = relative intracellular water, s = relative intracellular CPA moles.
Bath m1,m2 are molality / 0.3 Osm kg^-1; time is minutes / 4.33.
The independent reference uses the linear x-time system in Appendix A,
an augmented matrix exponential, and inversion of tau(x). No curve fitting.
"""

from dataclasses import dataclass
import math

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm
from scipy.optimize import brentq, minimize_scalar


@dataclass(frozen=True)
class Parameters:
    b: float = 1.62
    minutes_per_tau: float = 4.33
    gamma: float = 0.0168

    def __post_init__(self):
        if not all(math.isfinite(v) and v > 0 for v in (self.b, self.minutes_per_tau, self.gamma)):
            raise ValueError("Parameters must be positive and finite")


def validate_schedule(schedule):
    if not isinstance(schedule, list) or not schedule:
        raise ValueError("A nonempty piecewise-constant schedule is required")
    for step in schedule:
        for key in ("duration_min", "m1", "m2"):
            v = step.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"Invalid {key}")
        if step["duration_min"] <= 0 or step["m1"] <= 1e-4 or step["m2"] < 0:
            raise ValueError("duration must be positive, m1 > 1e-4; m2 nonnegative")


def rhs(tau, state, m1, m2, b):
    w, s = state[:2]
    if w <= 0 or not np.all(np.isfinite(state)):
        raise ValueError("Nonphysical transport state")
    return np.array([-m1 - m2 + (1 + s) / w, b * (m2 - s / w)])


def linear_reference(state, duration_min, m1, m2, p):
    """Independent Eq. A1 solution; integrate tau'=w in the same exponential."""
    if duration_min == 0:
        return np.asarray(state, dtype=float)
    matrix = np.array([[-m1-m2, 1, 0, 1],
                       [p.b*m2, -p.b, 0, 0],
                       [1, 0, 0, 0], [0, 0, 0, 0]], dtype=float)
    y0 = np.array([*state, 0, 1], dtype=float)
    target = duration_min / p.minutes_per_tau

    def evaluate(x):
        return expm(matrix * x) @ y0

    upper = max(1., target)
    for _ in range(60):
        if evaluate(upper)[2] >= target:
            break
        upper *= 2
    else:
        raise ValueError("Could not bracket transformed time")
    x = brentq(lambda x: evaluate(x)[2] - target, 0, upper, xtol=1e-13)
    return evaluate(x)[:2]


def simulate(schedule, p=Parameters(), initial=(1., 0.), rtol=1e-9,
             atol=1e-11, sample_interval_min=.02):
    """Restart at every bath switch; retain continuous state and cumulative exposure.

    Extrema are refined between dense samples. Exposure integrates intracellular
    EG molality over minutes; it has no fitted damage coefficient or survival link.
    """
    validate_schedule(schedule)
    if not (len(initial) == 2 and np.all(np.isfinite(initial)) and initial[0] > 0 and initial[1] >= 0):
        raise ValueError("Invalid initial water/CPA state")
    if not math.isfinite(sample_interval_min) or sample_interval_min <= 0:
        raise ValueError("Invalid sampling interval")
    state = np.array([*initial, 0.], dtype=float)
    elapsed, rows, boundaries = 0., [], []
    extrema = [initial[0] + p.gamma * initial[1]]
    for index, step in enumerate(schedule):
        duration = step["duration_min"]
        end_tau = duration / p.minutes_per_tau

        def augmented(t, y):
            return np.r_[rhs(t, y, step["m1"], step["m2"], p.b),
                         .3 * y[1] / y[0] * p.minutes_per_tau]

        sol = solve_ivp(augmented, (0, end_tau), state, method="DOP853",
                        rtol=rtol, atol=atol, dense_output=True,
                        max_step=min(end_tau, .1))
        if not sol.success:
            raise RuntimeError(sol.message)
        grid = np.linspace(0, end_tau, max(3, math.ceil(duration/sample_interval_min)+1))
        values = sol.sol(grid)
        if not np.all(np.isfinite(values)) or np.any(values[0] <= 0) or np.min(values[1]) < -1e-9:
            raise RuntimeError("Nonphysical solution")
        volumes = values[0] + p.gamma * values[1]
        extrema.extend([float(volumes.min()), float(volumes.max())])
        for sign in (1, -1):
            transformed = sign * volumes
            for j in range(1, len(grid)-1):
                if transformed[j] < transformed[j-1] and transformed[j] < transformed[j+1]:
                    opt = minimize_scalar(lambda t: sign * (sol.sol(t)[0] + p.gamma*sol.sol(t)[1]),
                                          bounds=(grid[j-1], grid[j+1]), method="bounded",
                                          options={"xatol": 1e-13})
                    extrema.append(float(sign * opt.fun))
        for j, tau in enumerate(grid):
            if index and j == 0:
                continue
            w, s, _ = values[:, j]
            rows.append({"time_min": float(elapsed+tau*p.minutes_per_tau),
                         "w": float(w), "s": float(s),
                         "relative_volume": float(w+p.gamma*s),
                         "intracellular_eg_osm_per_kg": float(.3*s/w),
                         "bath_m1": step["m1"], "bath_m2": step["m2"]})
        boundaries.append({"step": index, "initial": state[:2].tolist(),
                           "final": values[:2, -1].tolist()})
        state = values[:, -1]
        elapsed += duration
    return {"metrics": {"min_relative_volume": min(extrema),
                         "max_relative_volume": max(extrema),
                         "final_intracellular_eg_osm_per_kg": .3*state[1]/state[0],
                         "final_relative_volume": state[0]+p.gamma*state[1],
                         "intracellular_exposure_osm_min_per_kg": state[2],
                         "duration_min": elapsed},
            "boundaries": boundaries, "trajectory": rows}


def reference_error(schedule, simulation, p=Parameters()):
    """Check independent reference at 0, 25, 50, 75, 100% of each segment."""
    validate_schedule(schedule)
    state = np.array(simulation["boundaries"][0]["initial"], dtype=float)
    error = 0.
    for step, boundary in zip(schedule, simulation["boundaries"], strict=True):
        initial = state.copy()
        duration_tau = step["duration_min"] / p.minutes_per_tau
        numerical = solve_ivp(lambda t, y: rhs(t, y, step["m1"], step["m2"], p.b),
                              (0, duration_tau), boundary["initial"], method="DOP853",
                              rtol=1e-10, atol=1e-12, dense_output=True, max_step=.1)
        for fraction in (0., .25, .5, .75, 1.):
            analytic = linear_reference(initial, fraction*step["duration_min"], step["m1"], step["m2"], p)
            error = max(error, float(np.max(np.abs(analytic-numerical.sol(fraction*duration_tau)))))
        state = analytic
        error = max(error, float(np.max(np.abs(state-boundary["final"]))))
    return error
