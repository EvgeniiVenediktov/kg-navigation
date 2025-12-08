import carla
import math

MODE_LEFT = "left"
MODE_STRAIGHT = "straight"
MODE_RIGHT = "right"

class LaneChangeController:
    """Controller that can change left, hold lane, or change right."""
        
    def __init__(self, vehicle, world):
        self.vehicle = vehicle
        self.world = world
        self._map = world.get_map()
        
        # Lane offset in meters (negative = left, positive = right)
        self.lane_width = 3.5
        self.target_offset = 0.0  # Lateral offset from current path
        self.mode = MODE_STRAIGHT
        
    def set_lane_offset(self, offset):
        """
        Set target lane relative to current.
        Accepts -1/0/1 or MODE_LEFT/MODE_STRAIGHT/MODE_RIGHT.
        """
        if isinstance(offset, str):
            if offset == MODE_LEFT:
                offset = -1
            elif offset == MODE_RIGHT:
                offset = 1
            elif offset == MODE_STRAIGHT:
                offset = 0
            else:
                raise ValueError(f"Unknown lane offset value: {offset}")
        self.target_offset = float(offset) * self.lane_width
    
    def set_mode(self, mode):
        """Select lane change mode and update target offset accordingly."""
        if mode not in (MODE_LEFT, MODE_STRAIGHT, MODE_RIGHT):
            raise ValueError(f"Unknown mode: {mode}")
        self.mode = mode
        if mode == MODE_LEFT:
            self.set_lane_offset(-1)
        elif mode == MODE_RIGHT:
            self.set_lane_offset(1)
        else:
            self.set_lane_offset(0)
    
    def run_step(self, target_speed=80, emergency_brake=False):
        if emergency_brake:
            # Full stop regardless of current mode
            return carla.VehicleControl(throttle=0.0, steer=0.0, brake=1.0)
        
        v = self.vehicle.get_velocity()
        speed = 3.6 * math.sqrt(v.x**2 + v.y**2 + v.z**2)
        
        # Get waypoint ahead
        current_wp = self._map.get_waypoint(self.vehicle.get_location())
        lookahead = max(8.0, speed / 3.6)
        target_wp = current_wp.next(lookahead)[0]
        
        # Apply lateral offset for lane change
        target_loc = target_wp.transform.location
        if self.target_offset != 0:
            right_vec = target_wp.transform.get_right_vector()
            target_loc.x += right_vec.x * self.target_offset
            target_loc.y += right_vec.y * self.target_offset
        
        # Steering
        vehicle_tf = self.vehicle.get_transform()
        dx = target_loc.x - vehicle_tf.location.x
        dy = target_loc.y - vehicle_tf.location.y
        target_angle = math.degrees(math.atan2(dy, dx))
        error = target_angle - vehicle_tf.rotation.yaw
        
        while error > 180: error -= 360
        while error < -180: error += 360
        
        steer = max(-1.0, min(1.0, error / 60.0))
        
        # Throttle/brake
        speed_error = target_speed - speed
        if speed_error > 0:
            throttle = min(1.0, speed_error / 30.0)
            brake = 0.0
        else:
            throttle = 0.0
            brake = min(1.0, -speed_error / 30.0)
        
        return carla.VehicleControl(throttle=throttle, steer=steer, brake=brake)