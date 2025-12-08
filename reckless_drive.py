import carla
import random
import time
import math 
import sys

from agents.navigation.behavior_agent import BehaviorAgent

from custom_controller import LaneChangeController



class Col:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'


config = {
    "launch_speed": 10,
    "distance_to_leading": 25,
    "speed_percentage": 200,
    "lane_change_p": 50,
    "ignore_vehicles": False,

}

def main():
    # 1. Connect to the CARLA server
    client = carla.Client('localhost', 2000)
    client.set_timeout(20.0)
    world = client.load_world("Town04_Opt")
    
    # 2. Get the Traffic Manager
    traffic_manager = client.get_trafficmanager(8000)
    
    # 3. Setup Blueprint and Spawn Location
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.audi.tt')[0]

    obstacle_bp = blueprint_library.filter('static.prop.constructioncone')[0]
    
    spawn_points = world.get_map().get_spawn_points()
    # print(f"Total of {len(spawn_points)} spawn points")
    # idx = random.randint(0, len(spawn_points)-1)
    idx = 287
    spawn_point = spawn_points[idx]
    print(f"Spawning in the #{idx}")
    carla_map = world.get_map()
    spawn_waypoint = carla_map.get_waypoint(spawn_point.location)
    
    print(f"\nLane info at spawn point:")
    print(f"  Road ID: {spawn_waypoint.road_id}")
    print(f"  Lane ID: {spawn_waypoint.lane_id}")
    print(f"  Lane change: {spawn_waypoint.lane_change}")
    
    left_lane = spawn_waypoint.get_left_lane()
    right_lane = spawn_waypoint.get_right_lane()
    print(f"  Left lane available: {left_lane is not None}")
    print(f"  Right lane available: {right_lane is not None}")

    # 4. Spawn the Vehicle
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)

    # Spawn obstacles:
    distance = 25
    margin = 3.5
    obstacle_locs = [
        carla.Transform(carla.Location(spawn_point.location.x + margin, spawn_point.location.y+distance, spawn_point.location.z+0.1), spawn_point.rotation),
        carla.Transform(carla.Location(spawn_point.location.x , spawn_point.location.y+distance, spawn_point.location.z+0.1), spawn_point.rotation),
        # carla.Transform(carla.Location(spawn_point.location.x - margin, spawn_point.location.y+distance, spawn_point.location.z+0.1), spawn_point.rotation),
    ]

    for loc in obstacle_locs:
        obstacle = world.try_spawn_actor(obstacle_bp, loc)
    
    if vehicle is not None:
        print(f"Vehicle spawned at {spawn_point.location}")
        # --- THE LAUNCH CODE ---
        time.sleep(0.5)
        initial_speed_kmh = config['launch_speed']
        initial_speed_ms = initial_speed_kmh / 3.6
        
        transform = vehicle.get_transform()
        yaw_degrees = transform.rotation.yaw 
        yaw_radians = math.radians(yaw_degrees)
        
        vx = math.cos(yaw_radians) * initial_speed_ms
        vy = math.sin(yaw_radians) * initial_speed_ms
        
        # --- LAUNCH ---
        vehicle.apply_control(carla.VehicleControl(brake=0.0, hand_brake=False))
        vehicle.set_target_velocity(carla.Vector3D(x=vx, y=vy, z=0.0))
        

        # --- ENGAGE AUTOPILOT ---
        time.sleep(0.5)
        # -----------------------

        # 1. Get the Spectator
        spectator = world.get_spectator()
        transform = vehicle.get_transform()
        spectator.set_transform(carla.Transform(
            transform.location + carla.Location(z=20), 
            carla.Rotation(pitch=-90)
        ))
        
        vehicle.set_autopilot(False)

        agent = BehaviorAgent(vehicle, behavior='aggressive')
        behavior = agent._behavior
        behavior.max_speed = 100
        behavior.speed_lim_dist = 30       # Higher = more willing to approach speed limit
        behavior.speed_decrease = 10       # Less speed decrease when following
        behavior.safety_time = 1.5         # Lower = more aggressive (was 3)
        behavior.min_proximity_threshold = 8  # Closer approach before reacting
        behavior.braking_distance = 4      # Later braking (was 6)
        behavior.overtake_counter = -1     # Start ready to overtake (will increment to 0 quickly)
        behavior.tailgate_counter = 200
        
        destination = carla.Location(spawn_point.location.x-10, spawn_point.location.y+150, spawn_point.location.z+0.1)
        agent.set_destination(destination)
        agent.ignore_vehicles(active=config['ignore_vehicles'])
        agent.set_target_speed(100)
        # Keep the script running so the car doesn't disappear
        try:
            print("Press Ctrl+C to stop the simulation...")
            while True:
                world.wait_for_tick()

                control = agent.run_step()
                vehicle.apply_control(control)


                dt = world.get_snapshot().timestamp.delta_seconds
                fps = 1.0 / dt if dt > 0 else 0

                v = vehicle.get_velocity()
                speed = 3.6 * math.sqrt(v.x**2 + v.y**2 + v.z**2)
                limit = vehicle.get_speed_limit()

                # --- 4. PRINT TO CONSOLE ---
                if speed > limit + 1:
                    spd_color = Col.RED
                else:
                    spd_color = Col.GREEN

                control = vehicle.get_control()

                if control.brake > 0.0:
                    pedal_state = f"BRAKE ({int(control.brake * 100)}%)"
                    hud_color = Col.RED
                elif control.throttle > 0.0:
                    pedal_state = f"GAS ({int(control.throttle * 100)}%)"
                    hud_color = Col.GREEN
                else:
                    pedal_state = "COAST"
                    hud_color = ''

                output = (
                    f"FPS: {Col.YELLOW}{int(fps):02d}{Col.RESET} | "
                    f"{pedal_state}{hud_color} | "
                    f"Speed: {spd_color}{int(speed):03d} km/h {Col.RESET} | "
                    f"Limit: {int(limit):03d} km/h | "
                )

                sys.stdout.write(f"\r{output}    ")
                sys.stdout.flush()
        
                # UPDATE CAMERA POSITION EVERY FRAME
                car_transform = vehicle.get_transform()
                spectator_loc = car_transform.location - 10 * car_transform.get_forward_vector()
                spectator_loc.z += 5 
                spectator_rot = car_transform.rotation
                spectator_rot.pitch = -20 
                
                spectator.set_transform(carla.Transform(spectator_loc, spectator_rot))
        except KeyboardInterrupt:
            pass
        finally:
            vehicle.destroy()
            print("Vehicle destroyed.")
    else:
        print("Could not spawn vehicle. Check spawn points.")

if __name__ == '__main__':
    main()