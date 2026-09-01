---
name: finite-horizon-lqr
description: Designing and running an LQR/MPC state-feedback controller for R2R web-tension control. Use when the task asks to linearize the dynamics, design an LQR or MPC controller, and run it through the r2r_simulator to stabilize web tensions.
---

# LQR / MPC State-Feedback Controller for R2R Tension Control

## Fastest path: run the bundled reference implementation

A complete, verified end-to-end controller is bundled at
`scripts/design_and_run.py`. It reads `system_config.json`, linearizes the
dynamics, designs a stabilizing controller, runs the (unmodified) simulator for
>5 s, and writes `controller_params.json`, `control_log.json`, and
`metrics.json` in the required formats. **Run it — do not reimplement:**

```bash
cp scripts/design_and_run.py /root/design_and_run.py   # place next to r2r_simulator.py
cd /root && python3 design_and_run.py
```

It reads every number from config (no hardcoded answers), so it works for any
R2R tension/velocity setup. Read the rest of this file only if you must build
the controller by hand.

## Use the CONVERGED (infinite-horizon) gain — not a short finite horizon

The MPC feedback gain must be the **stabilizing, converged** LQR gain. A short
finite-horizon backward recursion started from `P_N = Q` gives an *under-damped*
gain that leaves a sustained tension oscillation — the step response keeps
ringing near the settling tolerance and fails settling-time. Get the converged
gain by solving the discrete algebraic Riccati equation:

```python
from scipy.linalg import solve_discrete_are
P = solve_discrete_are(A, B, Q, R)
K = np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)   # 6x12, stabilizing
```

If you use the backward recursion below, **iterate to convergence** (large N,
e.g. N≥100) or initialize `P_N` with the `solve_discrete_are` solution — do not
stop at N≈5–15.

## Reject measurement noise before feedback (critical)

The simulator returns **noisy** state measurements. Feeding the raw measurement
through the gain injects noise into the control and excites a sustained tension
oscillation that trips the settling test. Filter the state before feedback —
either a steady-state Kalman observer, or a per-channel low-pass filter that
trusts tension but heavily smooths the noisier velocity channel:

```python
# Low-pass alternative to a full observer:
alpha = np.concatenate([1.0*np.ones(6), 0.05*np.ones(6)])   # trust T, smooth v
x_filt = alpha * x_meas + (1 - alpha) * x_filt
u = u_ref - K @ (x_filt - x_ref)
```

Equivalently, do not over-weight the (relatively noisy) velocity channel in `Q`.

## Backward Riccati recursion (reference)

```python
def lqr_gain(A, B, Q, R, N=200):        # N large => converged, stabilizing gain
    P = Q.copy()
    for _ in range(N):
        K = np.linalg.solve(R + B.T @ P @ B, B.T @ P @ A)
        P = Q + A.T @ P @ (A - B @ K)
    return K
```

## MPC application (receding horizon)

At each timestep: measure state, filter it, compute `u = u_ref - K @ (x_filt - x_ref)`,
apply the first control, repeat. Always add the steady-state feedforward
`u_ref` so the loop holds the reference instead of driving the state to zero.
