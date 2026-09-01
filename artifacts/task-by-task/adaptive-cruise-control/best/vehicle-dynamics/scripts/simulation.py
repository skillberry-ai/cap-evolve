"""Simulation runner for Adaptive Cruise Control.

Reads PID gains from tuning_results.yaml at runtime (no embedded auto-tuning),
uses sensor_data.csv for lead-vehicle data, and writes simulation_results.csv.
Paths are relative to the current working directory so this file is generic.
"""

import os
import yaml
import pandas as pd
from acc_system import AdaptiveCruiseControl


def run_simulation(config_path, sensor_path, output_path, tuned_gains=None):
    """Run the ACC simulation and write results to output_path."""
    # Load configuration
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Apply tuned gains if provided (do NOT modify vehicle_params.yaml on disk)
    if tuned_gains:
        config['pid_speed_tuned'] = tuned_gains['pid_speed']
        config['pid_distance_tuned'] = tuned_gains['pid_distance']

    sensor_df = pd.read_csv(sensor_path)
    acc = AdaptiveCruiseControl(config)
    dt = config['simulation']['dt']

    results = []
    ego_speed = 0.0        # start at rest
    sim_distance = None     # simulated gap, propagated by physics (NOT re-read each step)

    for _, row in sensor_df.iterrows():
        time = row['time']
        lead_speed = row['lead_speed'] if pd.notna(row['lead_speed']) else None
        sensor_distance = row['distance'] if pd.notna(row['distance']) else None

        # Initialize the simulated gap when the lead vehicle first appears
        if lead_speed is not None and sim_distance is None:
            sim_distance = sensor_distance

        accel_cmd, mode, dist_error = acc.compute(ego_speed, lead_speed, sim_distance, dt)

        # TTC only defined while approaching (ego faster than lead)
        ttc = None
        if lead_speed is not None and sim_distance is not None:
            relative_speed = ego_speed - lead_speed
            if relative_speed > 0:
                ttc = sim_distance / relative_speed

        results.append({
            'time': time,
            'ego_speed': round(ego_speed, 3),
            'acceleration_cmd': round(accel_cmd, 3),
            'mode': mode,
            'distance_error': round(dist_error, 3) if dist_error is not None else '',
            'distance': round(sim_distance, 3) if sim_distance is not None else '',
            'ttc': round(ttc, 3) if ttc is not None else '',
        })

        # Physics update: integrate ego speed, then propagate the gap consistently
        ego_speed = max(0.0, ego_speed + accel_cmd * dt)
        if lead_speed is not None and sim_distance is not None:
            relative_speed = ego_speed - lead_speed
            sim_distance = sim_distance - relative_speed * dt
        elif lead_speed is None:
            sim_distance = None  # lead vehicle gone -> back to cruise

    pd.DataFrame(results).to_csv(output_path, index=False)
    print(f"Saved simulation results to {output_path}")
    return pd.DataFrame(results)


if __name__ == '__main__':
    tuned = None
    if os.path.exists('tuning_results.yaml'):
        with open('tuning_results.yaml', 'r') as f:
            tuned = yaml.safe_load(f)
    run_simulation(
        'vehicle_params.yaml',
        'sensor_data.csv',
        'simulation_results.csv',
        tuned_gains=tuned,
    )
