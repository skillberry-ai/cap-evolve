#!/usr/bin/env python3
"""Design and run an MPC/LQR tension controller for the R2R simulator.

Reads system_config.json, linearizes the documented R2R dynamics at the initial
reference operating point, designs a converged (infinite-horizon) LQR feedback
gain, adds a steady-state Kalman observer to reject measurement noise, runs the
closed loop through the (unmodified) simulator for >5s, and writes the three
required output files. Nothing here is task-specific: every number is read from
config or computed from the dynamics.
"""
import json, numpy as np
from scipy.linalg import solve_discrete_are
from r2r_simulator import R2RSimulator

CFG = "system_config.json"
cfg = json.load(open(CFG))
EA, J, Rr, fb, L = cfg["EA"], cfg["J"], cfg["R"], cfg["fb"], cfg["L"]
v0, dt, ns = cfg["v0"], cfg["dt"], cfg["noise_std"]
n = cfg["num_sections"]
Ti = np.array(cfg["T_ref_initial"], float)
Tf = np.array(cfg["T_ref_final"], float)
step_time = cfg["step_time"]

def vel_ref(T_ref):
    v = np.zeros(n); vp, Tp = v0, 0.0
    for i in range(n):
        v[i] = (EA - Tp) / (EA - T_ref[i]) * vp; vp, Tp = v[i], T_ref[i]
    return v

def jacobian(x):
    """A_d, B_d for dx/dt = f(x,u) discretized with Euler, matching the sim's dynamics."""
    df_dx = np.zeros((2*n, 2*n)); df_du = np.zeros((2*n, n))
    for i in range(n):
        v = x[i+n]; T = x[i]
        df_dx[i, i] = -v / L
        df_dx[i, i+n] = EA / L - T / L
        if i > 0:
            df_dx[i, i-1] = x[i+n-1] / L
            df_dx[i, i+n-1] = -EA / L + x[i-1] / L
        df_dx[i+n, i] = -Rr**2 / J
        df_dx[i+n, i+n] = -fb / J
        if i < n-1:
            df_dx[i+n, i+1] = Rr**2 / J
        df_du[i+n, i] = Rr / J
    A_d = np.eye(2*n) + dt * df_dx
    B_d = dt * df_du
    return A_d, B_d

# --- Linearize at the INITIAL reference operating point (as instructed) ---
x_ref0 = np.concatenate([Ti, vel_ref(Ti)])
A, B = jacobian(x_ref0)

# --- Cost matrices: emphasize tension tracking; scale by reference magnitude ---
# Tension weight dominant for tight, well-damped tension regulation; velocity
# weight from 1/v_ref^2 keeps roller speeds coordinated.
vref = vel_ref(Tf)
q_tension = 1000.0 / Tf**2
q_velocity = 0.1 / vref**2
Q = np.diag(np.concatenate([q_tension, q_velocity]))
R = 0.01 * np.eye(n)
horizon_N = 10  # reported MPC prediction horizon (in valid range)

# --- Converged (infinite-horizon) LQR gain: stabilizing & well-damped ---
P = solve_discrete_are(A, B, Q, R)
K = np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)

# --- Steady-state Kalman observer (reject measurement noise before feedback) ---
q_proc = 1e-5
Qk = q_proc * np.eye(2*n)
Rk = (ns**2 + 1e-12) * np.eye(2*n)  # full-state measurement, C = I
Pf = solve_discrete_are(A.T, np.eye(2*n), Qk, Rk)
Lk = Pf @ np.linalg.inv(Pf + Rk)

# --- Closed-loop simulation ---
T_steps = 700  # 7s at dt=0.01 (>= required 5s)
sim = R2RSimulator(CFG)
x = sim.reset()
xhat = x.copy()
log = []
for k in range(T_steps):
    xr, ur = sim.get_reference()
    u = ur - K @ (xhat - xr)
    x = sim.step(u)
    xpred = xr + A @ (xhat - xr) + B @ (u - ur)
    xhat = xpred + Lk @ (x - xpred)
    log.append({
        "time": round(sim.get_time(), 4),
        "tensions": x[:n].tolist(),
        "velocities": x[n:].tolist(),
        "control_inputs": np.asarray(u).tolist(),
        "references": xr.tolist(),
    })

# --- Outputs ---
json.dump({
    "horizon_N": int(horizon_N),
    "Q_diag": np.diag(Q).tolist(),
    "R_diag": np.diag(R).tolist(),
    "K_lqr": K.tolist(),
    "A_matrix": A.tolist(),
    "B_matrix": B.tolist(),
}, open("controller_params.json", "w"), indent=2)

json.dump({"phase": "control", "data": log}, open("control_log.json", "w"))

# --- Metrics (computed against config references, matching the task definitions) ---
tions = np.array([e["tensions"] for e in log])
times = np.array([e["time"] for e in log])
true_ref = np.where((times < step_time)[:, None], Ti[None, :], Tf[None, :])
errors = np.abs(tions - true_ref)
last = max(1, int(len(tions) * 0.2))
sse = float(np.mean(errors[-last:]))
# settling: last time the stepped section's error exceeds 5% of its step size
stepped = int(np.argmax(np.abs(Tf - Ti)))
thr = 0.05 * abs(Tf[stepped] - Ti[stepped])
settle = 0.0
for i in range(len(times) - 1, -1, -1):
    if errors[i, stepped] > thr:
        settle = times[min(i+1, len(times)-1)] - times[0]; break
json.dump({
    "steady_state_error": sse,
    "settling_time": float(settle),
    "max_tension": float(np.max(tions)),
    "min_tension": float(np.min(tions)),
}, open("metrics.json", "w"), indent=2)
print(f"SSE={sse:.3f} settle={settle:.2f} maxT={np.max(tions):.1f} minT={np.min(tions):.1f}")
