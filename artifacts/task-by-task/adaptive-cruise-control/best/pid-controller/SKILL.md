---
name: pid-controller
description: Use this skill when implementing PID control loops for adaptive cruise control, vehicle speed regulation, throttle/brake management, or any feedback control system requiring proportional-integral-derivative control.
---

# PID Controller Implementation

## Overview

A PID (Proportional-Integral-Derivative) controller is a feedback control mechanism used in industrial control systems. It continuously calculates an error value and applies a correction based on proportional, integral, and derivative terms.

## Control Law

```
output = Kp * error + Ki * integral(error) + Kd * derivative(error)
```

Where:
- `error` = setpoint - measured_value
- `Kp` = proportional gain (reacts to current error)
- `Ki` = integral gain (reacts to accumulated error)
- `Kd` = derivative gain (reacts to rate of change)

## Reference implementation — use it, do not hand-roll

A complete, tested `PIDController` is bundled at `scripts/pid_controller.py`. Copy it into
your working directory (`cp <skill_dir>/scripts/pid_controller.py .`) and use it as-is rather
than re-writing one from scratch. It is exactly the version shown below.

## Discrete-Time Implementation

Three details below are mandatory for a stable response (their absence is the usual cause of
overshoot/oscillation): (1) initialise `prev_error = None` and emit **zero** derivative on the
first `compute` so there is no derivative kick from a cold start; (2) low-pass filter the
derivative; (3) clamp the integral (`integral_max`) for anti-windup and clamp the output to the
actuator limits.

```python
class PIDController:
    """Discrete-time PID with anti-windup, filtered derivative, and output limiting."""

    def __init__(self, kp, ki, kd, output_min=None, output_max=None, integral_max=None):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_max = integral_max
        self.integral = 0.0
        self.prev_error = None      # None => no derivative kick on the first step
        self.prev_derivative = 0.0

    def reset(self):
        """Clear controller state."""
        self.integral = 0.0
        self.prev_error = None
        self.prev_derivative = 0.0

    def compute(self, error, dt):
        """Compute control output given error and timestep."""
        if dt <= 0:
            return 0.0

        # Proportional term
        p_term = self.kp * error

        # Integral term with anti-windup clamping
        self.integral += error * dt
        if self.integral_max is not None:
            self.integral = max(-self.integral_max, min(self.integral_max, self.integral))
        i_term = self.ki * self.integral

        # Derivative term, filtered; zero on the first call (prev_error is None)
        if self.prev_error is not None:
            raw = (error - self.prev_error) / dt
            alpha = 0.2  # low-pass filter coefficient
            derivative = alpha * raw + (1 - alpha) * self.prev_derivative
            self.prev_derivative = derivative
        else:
            derivative = 0.0
        d_term = self.kd * derivative
        self.prev_error = error

        # Total output, clamped to actuator limits
        output = p_term + i_term + d_term
        if self.output_min is not None:
            output = max(output, self.output_min)
        if self.output_max is not None:
            output = min(output, self.output_max)
        return output
```

## Anti-Windup

Integral windup occurs when output saturates but integral keeps accumulating. Solutions:

1. **Clamping**: Limit integral term magnitude
2. **Conditional Integration**: Only integrate when not saturated
3. **Back-calculation**: Reduce integral when output is clamped

## Tuning the gains — run the bundled grid search (do not hand-tune)

Deriving good gains by hand is slow and error-prone. A tested tuner is bundled at
`scripts/tune_pid.py`. It grid-searches the speed and distance gains against the real
`sensor_data.csv` and the task's performance targets, staying inside the allowed ranges
(`kp` in `(0,10)`, `ki` in `[0,5)`, `kd` in `[0,5)`), and writes the best gains to
`tuning_results.yaml`. If no gain set clears every target it still emits the best-scoring
candidate, so the file is always produced with valid gains.

Copy it next to `pid_controller.py` and `acc_system.py` and run it once, before the
simulation — execute it, do not reimplement the search:

```
cp <skill_dir>/scripts/tune_pid.py .
python3 tune_pid.py            # reads vehicle_params.yaml + sensor_data.csv, writes tuning_results.yaml
```

`tune_pid.py` is a design-time tool only; it is NOT imported by `simulation.py` (the simulation
loads the final gains from `tuning_results.yaml` at runtime, as required).

## Tuning Guidelines (background — prefer the bundled tuner above)

**Manual Tuning:**
1. Set Ki = Kd = 0
2. Increase Kp until acceptable response speed
3. Add Ki to eliminate steady-state error
4. Add Kd to reduce overshoot

**Effect of Each Gain:**
- Higher Kp -> faster response, more overshoot
- Higher Ki -> eliminates steady-state error, can cause oscillation
- Higher Kd -> reduces overshoot, sensitive to noise
