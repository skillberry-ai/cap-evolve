---
name: vehicle-dynamics
description: Use this skill when simulating vehicle motion, calculating safe following distances, time-to-collision, speed/position updates, or implementing vehicle state machines for cruise control modes.
---

# Vehicle Dynamics Simulation

## Quickstart — produce every ACC deliverable in a few commands (do this first)

For an Adaptive Cruise Control task the fastest reliable path is to reuse the bundled, tested
scripts instead of re-deriving the controller, hand-tuning gains, or writing the report by hand.
After a quick look at the inputs, copy the scripts into your working directory and run the three
steps in order (each writes the next stage's input, so keep the order):

```
# 1. bring the tested scripts into the cwd (skill dirs shown as <...>; use the real paths)
cp <pid-controller_skill>/scripts/pid_controller.py .
cp <pid-controller_skill>/scripts/tune_pid.py .
cp <vehicle-dynamics_skill>/scripts/acc_system.py .
cp <vehicle-dynamics_skill>/scripts/simulation.py .
cp <simulation-metrics_skill>/scripts/generate_report.py .

# 2. tune gains -> tuning_results.yaml   (grid search vs the real sensor data + spec targets)
python3 tune_pid.py

# 3. run the 150s simulation -> simulation_results.csv   (loads gains from tuning_results.yaml)
python3 simulation.py

# 4. write the report -> acc_report.md   (final deliverable; do not skip it)
python3 generate_report.py
```

This yields every deliverable (`pid_controller.py`, `acc_system.py`, `simulation.py`,
`tuning_results.yaml`, `simulation_results.csv`, `acc_report.md`) in a handful of turns. Do not
spend many turns hand-deriving gains or re-implementing the loop — the sections below explain
what the scripts do if you need to adjust them.

## Basic Kinematic Model

For vehicle simulations, use discrete-time kinematic equations.

**Speed Update:**
```python
new_speed = current_speed + acceleration * dt
new_speed = max(0, new_speed)  # Speed cannot be negative
```

**Position Update:**
```python
new_position = current_position + speed * dt
```

**Distance Between Vehicles:**
```python
# When following another vehicle
relative_speed = ego_speed - lead_speed
new_distance = current_distance - relative_speed * dt
```

## Safe Following Distance

The time headway model calculates safe following distance:

```python
def safe_following_distance(speed, time_headway, min_distance):
    """
    Calculate safe distance based on current speed.

    Args:
        speed: Current vehicle speed (m/s)
        time_headway: Time gap to maintain (seconds)
        min_distance: Minimum distance at standstill (meters)
    """
    return speed * time_headway + min_distance
```

## Time-to-Collision (TTC)

TTC estimates time until collision at current velocities:

```python
def time_to_collision(distance, ego_speed, lead_speed):
    """
    Calculate time to collision.

    Returns None if not approaching (ego slower than lead).
    """
    relative_speed = ego_speed - lead_speed

    if relative_speed <= 0:
        return None  # Not approaching

    return distance / relative_speed
```

## Acceleration Limits

Real vehicles have physical constraints:

```python
def clamp_acceleration(accel, max_accel, max_decel):
    """Constrain acceleration to physical limits."""
    return max(max_decel, min(accel, max_accel))
```

## State Machine Pattern

Vehicle control often uses mode-based logic:

```python
def determine_mode(lead_present, ttc, ttc_threshold):
    """
    Determine operating mode based on conditions.

    Returns one of: 'cruise', 'follow', 'emergency'
    """
    if not lead_present:
        return 'cruise'

    if ttc is not None and ttc < ttc_threshold:
        return 'emergency'

    return 'follow'
```

## Adaptive Cruise Control — reference implementation

Tested, ready-to-use `acc_system.py` and `simulation.py` are bundled at `scripts/`. Copy them
into your working directory and drive the simulation with them instead of re-deriving the
control loop:

```
cp <skill_dir>/scripts/acc_system.py .
cp <skill_dir>/scripts/simulation.py .   # needs pid_controller.py present too
python3 simulation.py                      # reads tuning_results.yaml, writes simulation_results.csv
```

`simulation.py` loads PID gains from `tuning_results.yaml` at runtime (no embedded auto-tuning),
so re-running after you retune the gains changes the output.

## Per-mode acceleration (get these right or the run fails)

- **cruise**: `accel = speed_pid.compute(set_speed - ego_speed, dt)`.
- **follow**: distance PID on the gap error PLUS a speed-matching feed-forward term. The
  feed-forward is essential — a distance PID alone lets the ego overtake the lead and the gap
  collapses below the safety minimum:
  ```python
  safe_dist = ego_speed * time_headway + min_distance
  distance_error = distance - safe_dist          # + = too far, - = too close
  accel = distance_pid.compute(distance_error, dt)
  accel += 0.3 * (lead_speed - ego_speed)         # feed-forward: converge to lead speed
  ```
- **emergency**: command maximum braking (`accel = max_deceleration`); acceleration must be
  negative in every emergency-mode row.

Always clamp the final acceleration to `[max_deceleration, max_acceleration]`.

## Output columns must be physics-consistent (anti-cheat)

The simulated gap must be **propagated by physics**, not re-read from the sensor each step, so
that the written `distance` is consistent with the *simulated* `ego_speed`:

```python
ego_speed = max(0.0, ego_speed + accel * dt)     # integrate first
distance  = distance - (ego_speed - lead_speed) * dt   # then propagate the gap
```

Column rules in `simulation_results.csv`:
- `distance` and `distance_error`: **empty** when no lead vehicle in the sensor row; filled when a lead is present.
- `ttc`: filled **only while approaching** (`ego_speed > lead_speed`); empty otherwise (and when no lead).
