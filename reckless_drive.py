import os
import time
import math
from itertools import product
from typing import List, Tuple

import carla

from knowledge_graph import KG
from custom_controller import *
from obstacles import (
    KG_INSTANCE_MAP,
    OBSTACLE_NAMES,
    CollisionDetector,
    ObstacleSpawner,
    RunStats,
)


class KgReasoning:
    def __init__(self, kg: KG):
        self.kg = kg

    def get_decision(self, obstacles: List[str]) -> Tuple[str, bool]:
        """Return (mode, brake) for left/straight/right lanes."""
        kg_instances = [KG_INSTANCE_MAP.get(name, name) for name in obstacles]

        behaviors = []
        for obstacle in kg_instances:
            behavior = self.kg.get_behavior_for_instance(obstacle)
            behaviors.append(behavior)

        print(f"Behaviors: {behaviors}")

        # If any lane is clear (BehaviorProceed), select it without brake
        if len(behaviors) >= 3:
            if behaviors[1] == "BehaviorProceed":
                return MODE_STRAIGHT, False
            if behaviors[0] == "BehaviorProceed":
                return MODE_LEFT, False
            if behaviors[2] == "BehaviorProceed":
                return MODE_RIGHT, False

        # All lanes blocked by same obstacle class
        if len(set(kg_instances)) == 1:
            return MODE_STRAIGHT, True

        hierarchy = self.kg.get_instances_sorted_by_importance(kg_instances)
        if not hierarchy:
            return MODE_STRAIGHT, True

        least_important = hierarchy[0]
        if len(kg_instances) >= 3:
            if kg_instances[1] == least_important:
                return MODE_STRAIGHT, True
            if kg_instances[0] == least_important:
                return MODE_LEFT, True
            if kg_instances[2] == least_important:
                return MODE_RIGHT, True

        return MODE_STRAIGHT, True


config = {
    "target_speed": 80,
    "scenario_timeout": float(os.getenv("SCENARIO_TIMEOUT", "3.0")),
    "launch_speed_kmh": float(os.getenv("LAUNCH_SPEED", "30.0")),
}

USE_CUSTOM_CONTROLLER = True
STATS_FILE = os.getenv("STATS_FILE", "run_stats_debug.jsonl")
FAST_MODE = os.getenv("FAST_MODE", "1") != "0"
MAX_COMBINATIONS = int(os.getenv("MAX_COMBINATIONS", "0"))


def _configure_world(world: carla.World) -> carla.WorldSettings:
    """Enable synchronous + no-rendering for faster batch runs."""
    original = world.get_settings()
    new_settings = world.get_settings()
    new_settings.synchronous_mode = True
    new_settings.fixed_delta_seconds = 0.05
    new_settings.no_rendering_mode = FAST_MODE
    world.apply_settings(new_settings)
    return original


def _reset_world(world: carla.World, original: carla.WorldSettings) -> None:
    world.apply_settings(original)


def _set_initial_speed(vehicle: carla.Vehicle, speed_kmh: float) -> None:
    """Kick off the ego with an initial forward speed."""
    speed_ms = speed_kmh / 3.6
    tf = vehicle.get_transform()
    yaw_rad = math.radians(tf.rotation.yaw)
    vx = math.cos(yaw_rad) * speed_ms
    vy = math.sin(yaw_rad) * speed_ms
    vehicle.apply_control(carla.VehicleControl(brake=0.0, hand_brake=False))
    vehicle.set_target_velocity(carla.Vector3D(x=vx, y=vy, z=0.0))


def _run_scenario(
    world: carla.World,
    vehicle_bp: carla.ActorBlueprint,
    spawn_point: carla.Transform,
    obstacle_locs: List[carla.Transform],
    kg_reasoning: KgReasoning,
    obstacles: Tuple[str, str, str],
) -> None:
    spawner = ObstacleSpawner(world)
    stats = RunStats()
    loc = carla.Transform(carla.Location(
        spawn_point.location.x - 2,
        spawn_point.location.y,
        spawn_point.location.z,
    ), spawn_point.rotation)
    vehicle = world.try_spawn_actor(vehicle_bp, loc)
    if vehicle is None:
        print("[WARN] Could not spawn vehicle for scenario, skipping.")
        return

    # spectator = world.get_spectator()
    # spectator.set_transform(
    #     carla.Transform(
    #         spawn_point.location + carla.Location(z=20),
    #         carla.Rotation(pitch=-90),
    #     )
    # )

    # Spawn obstacles (left, center, right)
    for name, loc in zip(obstacles, obstacle_locs):
        spawner.spawn(name, loc)
    stats.obstacles = spawner.get_names()

    collision_detector = CollisionDetector(vehicle, world, spawner, stats)
    controller = LaneChangeController(vehicle, world)

    # Give ego an initial forward velocity before control loop
    _set_initial_speed(vehicle, config["launch_speed_kmh"])

    mode, brake = kg_reasoning.get_decision(stats.obstacles.copy())
    stats.behavior = mode
    stats.brake_applied = brake
    controller.set_lane_offset(mode)

    start_time = time.time()
    try:
        while time.time() - start_time < config["scenario_timeout"]:
            world.tick()
            control = controller.run_step(
                target_speed=config["target_speed"], emergency_brake=brake
            )
            vehicle.apply_control(control)

            if stats.collided_with:
                break
    finally:
        stats.save(STATS_FILE)
        collision_detector.destroy()
        spawner.destroy_all()
        if vehicle.is_alive:
            vehicle.destroy()


def main():
    # 1. Connect to the CARLA server
    client = carla.Client("localhost", 2000)
    client.set_timeout(20.0)
    world = client.load_world("Town04_Opt")

    original_settings = _configure_world(world)

    blueprint_library = world.get_blueprint_library()
    vehicle_bp = blueprint_library.filter("vehicle.audi.tt")[0]

    spawn_points = world.get_map().get_spawn_points()
    idx = 287
    spawn_point = spawn_points[idx]
    print(f"Spawning in the #{idx}")

    # Spawn locations for three lanes: left, center, right
    distance = 25
    margin = 3.5
    obstacle_locs = [
        carla.Transform(
            carla.Location(
                spawn_point.location.x + margin,
                spawn_point.location.y + distance,
                spawn_point.location.z + 0.1,
            ),
            spawn_point.rotation,
        ),
        carla.Transform(
            carla.Location(
                spawn_point.location.x,
                spawn_point.location.y + distance,
                spawn_point.location.z + 0.1,
            ),
            spawn_point.rotation,
        ),
        carla.Transform(
            carla.Location(
                spawn_point.location.x - margin,
                spawn_point.location.y + distance,
                spawn_point.location.z + 0.1,
            ),
            spawn_point.rotation,
        ),
    ]

    # Prepare KG reasoning
    kg = KG()
    kg_reasoning = KgReasoning(kg)

    # Clear stats file for a fresh run
    open(STATS_FILE, "w", encoding="utf-8").close()

    all_combos = list(product(OBSTACLE_NAMES, repeat=3))
    if MAX_COMBINATIONS > 0:
        all_combos = all_combos[:MAX_COMBINATIONS]

    print(f"Running {len(all_combos)} obstacle combinations...")

    try:
        for i, combo in enumerate(all_combos, start=1):
            print(f"\nScenario {i}/{len(all_combos)}: {combo}")
            _run_scenario(world, vehicle_bp, spawn_point, obstacle_locs, kg_reasoning, combo)
    finally:
        _reset_world(world, original_settings)
        print(f"\nCompleted {len(all_combos)} scenarios. Stats saved to {STATS_FILE}")


if __name__ == "__main__":
    main()