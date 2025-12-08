import json
import math
import time
from dataclasses import dataclass, field
from typing import List, Optional

import carla

# Supported obstacle names selected before spawning
OBSTACLE_NAMES = [
    "car",
    "bottle",
    "person",
    "box",
    "cat",
    "dog",
    "bird",
    "bag",
]

# String name -> CARLA blueprint id mapping
OBSTACLE_BLUEPRINTS = {
    "person": "walker.pedestrian.0001",
    "car": "vehicle.audi.a2",
    "box": "static.prop.box01",
    "cat": "static.prop.box02",  # Substitute; CARLA has no cat actor
    "dog": "static.prop.box03",  # Substitute; CARLA has no dog actor
    "bird": "static.prop.plasticbag",  # Substitute lightweight prop
    "bottle": "static.prop.colacan",
    "bag": "static.prop.plasticbag",
}

# Detection name -> KG instance name mapping
KG_INSTANCE_MAP = {
    "person": "DetectedPerson",
    "car": "DetectedCar",
    "box": "DetectedBox",
    "cat": "DetectedCat",
    "dog": "DetectedDog",
    "bird": "DetectedBird",
    "bottle": "DetectedBottle",
    "bag": "DetectedBag",
}


@dataclass
class RunStats:
    obstacles: List[str] = field(default_factory=list)  # e.g., ["bag", "car", "bottle"]
    behavior: str = ""  # "left" | "right" | "straight"
    brake_applied: bool = False
    collision_speed: float = 0.0  # km/h at collision, 0 if none
    collided_with: Optional[str] = None  # obstacle name or None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "obstacles": self.obstacles,
            "behavior": self.behavior,
            "brake_applied": self.brake_applied,
            "collision_speed": round(self.collision_speed, 2),
            "collided_with": self.collided_with,
            "timestamp": self.timestamp,
        }

    def save(self, filename: str) -> None:
        """Append run statistics as JSONL."""
        with open(filename, "a", encoding="utf-8") as f:
            f.write(json.dumps(self.to_dict()) + "\n")


class ObstacleSpawner:
    def __init__(self, world: carla.World):
        self.world = world
        self.bp_library = world.get_blueprint_library()
        self.spawned: List[tuple[str, carla.Actor]] = []  # (name, actor)

    def spawn(self, name: str, transform: carla.Transform) -> Optional[carla.Actor]:
        """Spawn obstacle by string name. Returns actor or None."""
        bp_id = OBSTACLE_BLUEPRINTS.get(name)
        if not bp_id:
            print(f"[ObstacleSpawner] Unknown obstacle: {name}")
            return None

        bp = self.bp_library.find(bp_id)
        actor = self.world.try_spawn_actor(bp, transform)

        if actor:
            # Enable physics for props
            if "static.prop" in bp_id:
                actor.set_simulate_physics(True)
            # Freeze pedestrians
            elif "walker" in bp_id:
                actor.apply_control(carla.WalkerControl(speed=0.0))
            # Freeze vehicles
            elif "vehicle" in bp_id:
                actor.set_autopilot(False)
                actor.apply_control(carla.VehicleControl(brake=1.0, hand_brake=True))

            self.spawned.append((name, actor))

        return actor

    def get_names(self) -> List[str]:
        """Return list of spawned obstacle names."""
        return [name for name, _ in self.spawned]

    def find_collided(self, collision_actor_id: int) -> Optional[str]:
        """Find obstacle name by actor id."""
        for name, actor in self.spawned:
            if actor.id == collision_actor_id:
                return name
        return None

    def destroy_all(self) -> None:
        for _, actor in self.spawned:
            if actor and actor.is_alive:
                actor.destroy()
        self.spawned.clear()


class CollisionDetector:
    def __init__(self, vehicle: carla.Vehicle, world: carla.World, obstacle_spawner: ObstacleSpawner, stats: RunStats):
        self.stats = stats
        self.spawner = obstacle_spawner
        self.vehicle = vehicle

        bp = world.get_blueprint_library().find("sensor.other.collision")
        self.sensor = world.spawn_actor(bp, carla.Transform(), attach_to=vehicle)
        self.sensor.listen(self._on_collision)

    def _on_collision(self, event: carla.CollisionEvent) -> None:
        v = self.vehicle.get_velocity()
        speed = 3.6 * math.sqrt(v.x**2 + v.y**2 + v.z**2)

        self.stats.collision_speed = speed
        self.stats.collided_with = self.spawner.find_collided(event.other_actor.id)

        print(f"\n[COLLISION] Speed: {speed:.1f} km/h, Object: {self.stats.collided_with}")

    def destroy(self) -> None:
        if self.sensor and self.sensor.is_alive:
            self.sensor.destroy()

