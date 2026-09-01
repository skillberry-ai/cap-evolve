"""PID Controller implementation with anti-windup protection."""

class PIDController:
    """Discrete-time PID controller with anti-windup and output limiting."""

    def __init__(self, kp, ki, kd, output_min=None, output_max=None, integral_max=None):
        """
        Initialize PID controller.

        Args:
            kp: Proportional gain
            ki: Integral gain
            kd: Derivative gain
            output_min: Minimum output value (optional)
            output_max: Maximum output value (optional)
            integral_max: Maximum integral term magnitude for anti-windup (optional)
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.integral_max = integral_max

        self.integral = 0.0
        self.prev_error = None
        self.prev_derivative = 0.0

    def reset(self):
        """Reset controller state."""
        self.integral = 0.0
        self.prev_error = None
        self.prev_derivative = 0.0

    def compute(self, error, dt):
        """
        Compute control output.

        Args:
            error: Current error (setpoint - measured)
            dt: Time step in seconds

        Returns:
            Control output value
        """
        if dt <= 0:
            return 0.0

        # Proportional term
        p_term = self.kp * error

        # Integral term with anti-windup
        self.integral += error * dt
        if self.integral_max is not None:
            self.integral = max(-self.integral_max, min(self.integral_max, self.integral))
        i_term = self.ki * self.integral

        # Derivative term with filtering
        if self.prev_error is not None:
            raw_derivative = (error - self.prev_error) / dt
            # Low-pass filter on derivative (alpha = 0.2)
            alpha = 0.2
            derivative = alpha * raw_derivative + (1 - alpha) * self.prev_derivative
            self.prev_derivative = derivative
        else:
            derivative = 0.0

        d_term = self.kd * derivative
        self.prev_error = error

        # Total output
        output = p_term + i_term + d_term

        # Output clamping
        if self.output_min is not None:
            output = max(self.output_min, output)
        if self.output_max is not None:
            output = min(self.output_max, output)

        return output
