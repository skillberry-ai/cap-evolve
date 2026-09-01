"""Design-time PID gain tuner for the ACC speed and distance loops.

Grid-searches gains against the real sensor data and the task's performance
targets, then writes the best gains to tuning_results.yaml. This is a
DESIGN-TIME tool only: it is NOT imported by simulation.py -- simulation.py
loads the final gains from tuning_results.yaml at runtime (constraint: no
embedded auto-tuning in the simulation).

Run it once, before the simulation, to produce tuning_results.yaml:

    cp <pid-controller_skill>/scripts/tune_pid.py .
    python3 tune_pid.py          # writes tuning_results.yaml in the cwd

It needs pid_controller.py and acc_system.py present in the cwd (copy them from
their skills first). All paths are relative to the cwd, so it is task-generic.

Gains are searched only inside the allowed ranges (kp in (0,10), ki in [0,5),
kd in [0,5)) and the objective is the stated ACC spec (speed rise time < 10s,
overshoot < 5%, steady-state error < 0.5 m/s; follow-distance steady-state
error < 2m and minimum gap > 5m). If no gain set clears every target the
tuner still emits the best-scoring candidate it found (never crashes / never
leaves tuning_results.yaml missing), so the pipeline always has valid gains.
"""

import itertools

import pandas as pd
import yaml

from acc_system import AdaptiveCruiseControl


def load_base_config(path='vehicle_params.yaml'):
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def _simulate(config, sensor):
    """Run the ACC loop with the given config; return per-step arrays."""
    acc = AdaptiveCruiseControl(config)
    dt = config['simulation']['dt']

    ego_speed = 0.0
    sim_distance = None
    lead_present_prev = False

    times, speeds, distances, dist_errors, modes = [], [], [], [], []

    for _, row in sensor.iterrows():
        lead_speed = None if pd.isna(row['lead_speed']) else float(row['lead_speed'])
        lead_present = lead_speed is not None
        if lead_present and not lead_present_prev:
            sim_distance = float(row['distance'])
        lead_present_prev = lead_present

        distance_input = sim_distance if lead_present else None
        accel, mode, distance_error = acc.compute(ego_speed, lead_speed, distance_input, dt)

        times.append(row['time'])
        speeds.append(ego_speed)
        distances.append(distance_input)
        dist_errors.append(distance_error)
        modes.append(mode)

        next_ego_speed = max(0.0, ego_speed + accel * dt)
        if lead_present:
            sim_distance = sim_distance + (lead_speed - ego_speed) * dt
        ego_speed = next_ego_speed

    return pd.DataFrame({
        'time': times, 'ego_speed': speeds, 'distance': distances,
        'distance_error': dist_errors, 'mode': modes,
    })


def _rise_time(times, values, target):
    t10 = t90 = None
    for t, v in zip(times, values):
        if t10 is None and v >= 0.1 * target:
            t10 = t
        if t90 is None and v >= 0.9 * target:
            t90 = t
            break
    if t10 is not None and t90 is not None:
        return t90 - t10
    return None


def _overshoot_percent(values, target):
    max_val = max(values)
    if max_val <= target:
        return 0.0
    return ((max_val - target) / target) * 100


def _score_speed(df, set_speed):
    seg = df[df['time'] <= 29.9]
    times = seg['time'].tolist()
    values = seg['ego_speed'].tolist()
    rt = _rise_time(times, values, set_speed)
    ov = _overshoot_percent(values, set_speed)
    ss_vals = [v for t, v in zip(times, values) if t >= 25.0]
    ss_err = abs(set_speed - sum(ss_vals) / len(ss_vals)) if ss_vals else float('inf')
    if rt is None:
        return None
    return rt, ov, ss_err


def _score_distance(df):
    follow = df[df['mode'].isin(['follow', 'emergency'])]
    if len(follow) == 0:
        return float('inf'), float('inf')
    min_dist = follow['distance'].min()
    stable = follow[follow['time'].between(55.0, 70.0)]
    ss_err = abs(stable['distance_error']).mean() if len(stable) else float('inf')
    return min_dist, ss_err


def tune_speed(base_config, sensor, set_speed):
    kp_vals = [0.3, 0.5, 0.7, 1.0, 1.5, 2.0]
    ki_vals = [0.0, 0.02, 0.05, 0.1]
    kd_vals = [0.0, 0.1, 0.2, 0.4]

    passing, best_effort, best_key = [], None, None
    for kp, ki, kd in itertools.product(kp_vals, ki_vals, kd_vals):
        config = dict(base_config)
        config['pid_speed'] = {'kp': kp, 'ki': ki, 'kd': kd}
        config['pid_distance'] = base_config['pid_distance']
        result = _score_speed(_simulate(config, sensor), set_speed)
        if result is None:
            continue
        rt, ov, ss_err = result
        key = (rt, ov, ss_err)
        # track overall best in case nothing clears the spec
        score = rt + ov + ss_err
        if best_key is None or score < best_key:
            best_key, best_effort = score, (kp, ki, kd)
        if rt < 10.0 and ov < 5.0 and ss_err < 0.5:
            passing.append((rt, ov, ss_err, kp, ki, kd))

    if passing:
        passing.sort(key=lambda c: (c[0], c[1], c[2]))
        c = passing[0]
        return {'kp': c[3], 'ki': c[4], 'kd': c[5]}
    kp, ki, kd = best_effort
    return {'kp': kp, 'ki': ki, 'kd': kd}


def tune_distance(base_config, sensor, speed_gains):
    kp_vals = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
    ki_vals = [0.0, 0.01, 0.02, 0.05]
    kd_vals = [0.0, 0.1, 0.2, 0.4, 0.6]

    passing, best_effort, best_key = [], None, None
    for kp, ki, kd in itertools.product(kp_vals, ki_vals, kd_vals):
        config = dict(base_config)
        config['pid_speed'] = speed_gains
        config['pid_distance'] = {'kp': kp, 'ki': ki, 'kd': kd}
        min_dist, ss_err = _score_distance(_simulate(config, sensor))
        # penalise unsafe gaps hard; otherwise minimise steady-state error
        score = ss_err + (1000.0 if min_dist <= 5.0 else 0.0)
        if best_key is None or score < best_key:
            best_key, best_effort = score, (kp, ki, kd)
        if min_dist > 5.0 and ss_err < 2.0:
            passing.append((ss_err, min_dist, kp, ki, kd))

    if passing:
        passing.sort(key=lambda c: (c[0], -c[1]))
        c = passing[0]
        return {'kp': c[2], 'ki': c[3], 'kd': c[4]}
    kp, ki, kd = best_effort
    return {'kp': kp, 'ki': ki, 'kd': kd}


def main():
    base_config = load_base_config()
    sensor = pd.read_csv('sensor_data.csv')
    set_speed = base_config['acc_settings']['set_speed']

    speed_gains = tune_speed(base_config, sensor, set_speed)
    distance_gains = tune_distance(base_config, sensor, speed_gains)

    tuning_results = {'pid_speed': speed_gains, 'pid_distance': distance_gains}
    with open('tuning_results.yaml', 'w') as f:
        yaml.dump(tuning_results, f, default_flow_style=False, sort_keys=False)

    print(f"Final speed gains:    {speed_gains}")
    print(f"Final distance gains: {distance_gains}")
    print("Wrote tuning_results.yaml")


if __name__ == '__main__':
    main()
