import carla
import math

class LaneChangeController:
    """Minimal controller that changes lanes based on obstacle decisions."""
    
    def __init__(self, vehicle, world):
        self.vehicle = vehicle
        self.world = world
        self._map = world.get_map()
        
        # Lane offset in meters (negative = left, positive = right)
        self.lane_width = 3.5
        self.target_offset = 0.0  # Lateral offset from current path
        
    def set_lane_offset(self, offset):
        """
        Set target lane relative to current.
        -1 = one lane left, +1 = one lane right, 0 = stay
        """
        self.target_offset = offset * self.lane_width
    
    def run_step(self, target_speed=80):
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