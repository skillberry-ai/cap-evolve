---
name: mpc-horizon-tuning
description: Selecting MPC prediction horizon and cost matrices for web handling.
---

# MPC Tuning for Tension Control

> **Feedback gain vs. horizon.** `horizon_N` below is only the *reported* MPC
> prediction horizon. The state-feedback gain `K` that actually stabilizes the
> loop must be the **converged, infinite-horizon** LQR gain
> (`scipy.linalg.solve_discrete_are`), NOT a short finite-horizon gain — a short
> recursion is under-damped and leaves a ringing tension oscillation that fails
> settling-time. See the `finite-horizon-lqr` skill, which bundles a verified
> end-to-end `scripts/design_and_run.py` (linearize → LQR → run → metrics).

## Prediction Horizon Selection

**Horizon N** affects performance and computation:
- Too short (N < 5): Poor disturbance rejection
- Too long (N > 20): Excessive computation
- Rule of thumb: N ≈ 2-3× settling time / dt

For R2R systems with dt=0.01s: **N = 5-15** typical

## Cost Matrix Design

**State cost Q**: Emphasize tension tracking
```python
Q_tension = 100 / T_ref²  # High weight on tensions
Q_velocity = 0.1 / v_ref²  # Lower weight on velocities
Q = diag([Q_tension × 6, Q_velocity × 6])
```

**Control cost R**: Penalize actuator effort
```python
R = 0.01-0.1 × eye(n_u)  # Smaller = more aggressive
```

**Measurement noise caution:** the velocity channel is measured with relatively
high noise. Over-weighting velocity in `Q` (or feeding raw measurements through a
high gain) makes the controller chase noise and injects a sustained tension
oscillation. Either weight velocity lightly, raise `R` for a smoother loop, or —
best — filter the state (Kalman observer / low-pass the velocity channel) before
computing `u = u_ref - K @ (x_filt - x_ref)`.

## Trade-offs

| Higher Q | Effect |
|----------|--------|
| Faster tracking | More control effort |
| Lower steady-state error | More aggressive transients |

| Higher R | Effect |
|----------|--------|
| Smoother control | Slower response |
| Less actuator wear | Higher tracking error |

## Terminal Cost

Use LQR solution for terminal cost to guarantee stability:
```python
P = solve_continuous_are(A, B, Q, R)
```
