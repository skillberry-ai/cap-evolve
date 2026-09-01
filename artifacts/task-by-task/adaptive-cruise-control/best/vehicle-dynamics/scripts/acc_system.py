"""Adaptive Cruise Control system with cruise, follow, and emergency modes."""

from pid_controller import PIDController
import math


class AdaptiveCruiseControl:
    """ACC system with three operating modes."""

    def __init__(self, config):
        """
        Initialize ACC system.

        Args:
            config: Dictionary with vehicle and ACC parameters
        """
        self.set_speed = config['acc_settings']['set_speed']
        self.time_headway = config['acc_settings']['time_headway']
        self.min_distance = config['acc_settings']['min_distance']
        self.emergency_ttc = config['acc_settings']['emergency_ttc_threshold']

        self.max_accel = config['vehicle']['max_acceleration']
        self.max_decel = config['vehicle']['max_deceleration']

        # Speed controller for cruise mode - use tuned gains
        pid_speed = config.get('pid_speed_tuned', config['pid_speed'])
        self.speed_controller = PIDController(
            kp=pid_speed['kp'],
            ki=pid_speed['ki'],
            kd=pid_speed['kd'],
            output_min=self.max_decel,
            output_max=self.max_accel,
            integral_max=10.0
        )

        # Distance controller for follow mode - use tuned gains
        pid_dist = config.get('pid_distance_tuned', config['pid_distance'])
        self.distance_controller = PIDController(
            kp=pid_dist['kp'],
            ki=pid_dist['ki'],
            kd=pid_dist['kd'],
            output_min=self.max_decel,
            output_max=self.max_accel,
            integral_max=20.0
        )

        self.mode = 'cruise'
        self.prev_mode = 'cruise'

    def calculate_safe_distance(self, ego_speed):
        """Calculate safe following distance based on speed."""
        return ego_speed * self.time_headway + self.min_distance

    def calculate_ttc(self, distance, ego_speed, lead_speed):
        """Calculate time-to-collision."""
        relative_speed = ego_speed - lead_speed
        if relative_speed <= 0 or distance <= 0:
            return float('inf')
        return distance / relative_speed

    def determine_mode(self, lead_present, distance, ego_speed, lead_speed):
        """Determine operating mode based on current situation."""
        if not lead_present:
            return 'cruise'

        ttc = self.calculate_ttc(distance, ego_speed, lead_speed)
        if ttc < self.emergency_ttc:
            return 'emergency'

        return 'follow'

    def compute(self, ego_speed, lead_speed, distance, dt):
        """
        Compute acceleration command.

        Args:
            ego_speed: Current ego vehicle speed (m/s)
            lead_speed: Lead vehicle speed (m/s) or None if not present
            distance: Distance to lead vehicle (m) or None if not present
            dt: Time step (seconds)

        Returns:
            Tuple of (acceleration_cmd, mode, distance_error)
        """
        lead_present = lead_speed is not None and distance is not None

        # Determine mode
        if lead_present:
            self.mode = self.determine_mode(True, distance, ego_speed, lead_speed)
        else:
            self.mode = 'cruise'

        # Reset controllers on mode change
        if self.mode != self.prev_mode:
            if self.mode == 'cruise':
                self.speed_controller.reset()
            elif self.mode == 'follow':
                self.distance_controller.reset()
        self.prev_mode = self.mode

        # Compute acceleration based on mode
        distance_error = None

        if self.mode == 'cruise':
            # Cruise mode: maintain set speed
            speed_error = self.set_speed - ego_speed
            accel_cmd = self.speed_controller.compute(speed_error, dt)

        elif self.mode == 'follow':
            # Follow mode: maintain safe distance
            safe_dist = self.calculate_safe_distance(ego_speed)
            distance_error = distance - safe_dist  # Positive = too far, negative = too close

            # Use distance controller
            accel_cmd = self.distance_controller.compute(distance_error, dt)

            # Also consider matching lead speed
            speed_diff = lead_speed - ego_speed
            accel_cmd += 0.3 * speed_diff  # Feed-forward term

        else:  # emergency
            # Emergency mode: maximum braking
            accel_cmd = self.max_decel
            safe_dist = self.calculate_safe_distance(ego_speed)
            distance_error = distance - safe_dist

        # Clamp to physical limits
        accel_cmd = max(self.max_decel, min(self.max_accel, accel_cmd))

        return accel_cmd, self.mode, distance_error
