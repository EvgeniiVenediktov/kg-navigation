import carla
import random
import time
import math 
import sys

class Col:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    RESET = '\033[0m'


def main():
    # 1. Connect to the CARLA server
    client = carla.Client('localhost', 2000)
    client.set_timeout(10.0)
    # world = client.get_world()
    # print(client.get_available_maps())
    world = client.load_world("Town04_Opt")
    
    # 2. Get the Traffic Manager
    # The default port for the Traffic Manager is 8000
    traffic_manager = client.get_trafficmanager(8000)
    
    # OPTIONAL: Set global behavior for the Traffic Manager
    # traffic_manager.set_global_distance_to_leading_vehicle(2.5) # Maintain 2.5m distance
    # traffic_manager.set_synchronous_mode(True) # Sync with simulation tick if you use it

    # 3. Setup Blueprint and Spawn Location
    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter('vehicle.audi.tt')[0]
    
    spawn_points = world.get_map().get_spawn_points()
    # print(f"Total of {len(spawn_points)} spawn points")
    # idx = random.randint(0, len(spawn_points)-1)
    idx = 287
    spawn_point = spawn_points[idx]
    print(f"Spawning in the #{idx}")

    # 4. Spawn the Vehicle
    vehicle = world.try_spawn_actor(vehicle_bp, spawn_point)
    
    if vehicle is not None:
        print(f"Vehicle spawned at {spawn_point.location}")
        # --- THE LAUNCH CODE ---
        time.sleep(0.5)
        initial_speed_kmh = 250
        initial_speed_ms = initial_speed_kmh / 3.6
        
        # Get the current YAW (Left/Right direction) only. Ignore Pitch (Up/Down).
        transform = vehicle.get_transform()
        yaw_degrees = transform.rotation.yaw 
        yaw_radians = math.radians(yaw_degrees)

        # Calculate vector using basic trigonometry (X=Cos, Y=Sin)
        # This ensures the vector is perfectly parallel to the horizon.
        vx = math.cos(yaw_radians) * initial_speed_ms
        vy = math.sin(yaw_radians) * initial_speed_ms
        
        # --- STEP 3: LAUNCH ---
        # Release brakes
        vehicle.apply_control(carla.VehicleControl(brake=0.0, hand_brake=False))
        
        # Apply Velocity
        # We set Z=0 to ensure we don't shoot it into the sky or ground
        vehicle.set_target_velocity(carla.Vector3D(x=vx, y=vy, z=0.0))
        

        # --- STEP 4: ENGAGE AUTOPILOT ---
        # Give physics 0.1s to register the speed before AI takes over steering
        time.sleep(0.5)
        # -----------------------

        # 1. Get the Spectator (the camera you control in the simulator)
        spectator = world.get_spectator()

        # 2. Calculate a camera position behind and above the car
        # We take the spawn point's location and rotation
        transform = vehicle.get_transform()
        
        # Option A: Top-Down View (Good for debugging pathing)
        # Place camera 20 meters straight up, looking down (-90 degrees pitch)
        spectator.set_transform(carla.Transform(
            transform.location + carla.Location(z=20), 
            carla.Rotation(pitch=-90)
        ))
        
        # 5. Enable Autopilot
        # IMPORTANT: You must pass the Traffic Manager's port if it's not default, 
        # but usually vehicle.set_autopilot(True) registers it to the default TM (8000).
        vehicle.set_autopilot(True) 

        # 6. Set the Speed Strategy
        # The value is a PERCENTAGE DIFFERENCE from the speed limit.
        # Positive = Slower than limit.
        # Negative = Faster than limit.
        
        # Example: Drive at 80% of the speed limit (Default behavior is ~30)
        # traffic_manager.vehicle_percentage_speed_difference(vehicle, 20) 
        
        # Example: Drive at 120% of the speed limit (20% faster)
        traffic_manager.vehicle_percentage_speed_difference(vehicle, -200)

        # 2. Rules: Ignore all traffic lights and stop signs
        traffic_manager.ignore_lights_percentage(vehicle, 100)
        traffic_manager.ignore_signs_percentage(vehicle, 100)

        # 3. Perception: Ignore other cars (Blind Driver)
        # The car will not brake for vehicles in front of it.
        traffic_manager.ignore_vehicles_percentage(vehicle, 100)
        
        # 4. Safety Distance: 0 meters
        traffic_manager.distance_to_leading_vehicle(vehicle, 0.0)


        # Keep the script running so the car doesn't disappear
        try:
            print("Press Ctrl+C to stop the simulation...")
            while True:
                world.wait_for_tick()
                # world.tick()

                control = vehicle.get_control()

                # 2. Force FULL THROTTLE and NO BRAKES
                #    We overwrite whatever speed safety the TM calculated.
                control.throttle = 1.0 
                control.brake = 0.0
                control.hand_brake = False

                v = vehicle.get_velocity()
                speed = 3.6 * math.sqrt(v.x**2 + v.y**2 + v.z**2)
                limit = vehicle.get_speed_limit()
                dt = world.get_snapshot().timestamp.delta_seconds
                fps = 1.0 / dt if dt > 0 else 0

                # --- 3. COLOR LOGIC ---
                # If speed > limit + 1 (tolerance), make it RED. Else GREEN.
                if speed > limit + 1:
                    spd_color = Col.RED
                else:
                    spd_color = Col.GREEN

                # --- 4. PRINT TO CONSOLE ---
                # \r returns cursor to start of line. end='' prevents new line.
                # We pad with spaces to ensure the line clears previous longer text.
                output = (
                    f"FPS: {Col.YELLOW}{int(fps):02d}{Col.RESET} | "
                    f"Limit: {int(limit):03d} km/h | "
                    f"Speed: {spd_color}{int(speed):03d} km/h {Col.RESET}"
                )

                sys.stdout.write(f"\r{output}    ")
                sys.stdout.flush()
        
                # UPDATE CAMERA POSITION EVERY FRAME
                # Get the current location of the moving car
                car_transform = vehicle.get_transform()
                
                # Calculate position: 10 meters behind, 5 meters up
                # We use the car's "forward vector" to know which way is "behind"
                spectator_loc = car_transform.location - 10 * car_transform.get_forward_vector()
                spectator_loc.z += 5 
                
                # Make the camera look at the car (same rotation as car, but tilted down slightly)
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