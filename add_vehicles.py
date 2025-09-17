import carla
import random

# Connect to the client and retrieve the world object
client = carla.Client('localhost', 2000)
world = client.get_world()

# Get the blueprint library and filter for vehicles
blueprint_library = world.get_blueprint_library()
vehicle_blueprints = blueprint_library.filter('vehicle.*')


spawn_points = world.get_map().get_spawn_points()

# Spawn 50 vehicles randomly distributed throughout the map 
# for each spawn point, we choose a random vehicle from the blueprint library
for i in range(0,25):
    world.try_spawn_actor(random.choice(vehicle_blueprints), random.choice(spawn_points))

for vehicle in world.get_actors().filter('*vehicle*'):
    vehicle.set_autopilot(True)