from rdflib import Graph, Namespace
from rdflib.namespace import RDF, RDFS


graph = Graph()
# Define a namespace for our custom vocabulary
EX = Namespace("http://my-robotic-vision-kg.org/")
graph.bind("ex", EX)
graph.bind("rdfs", RDFS)
graph.bind("rdf", RDF)

# Hierarchy

# Types
person = EX.Person
bottle = EX.Bottle
plastic_bag = EX.PlasticBag
cardboard_box = EX.CardboardBox
bird = EX.Bird
dog = EX.Dog
cat = EX.Cat

# Classes
animal = EX.Animal
light_obstacle = EX.LightObstacle
living_being = EX.LivingBeing
heavy_obstacle = EX.HeavyObstacle

# Behaviors
behavior_avoid = EX.BehaviorAvoid
behavior_proceed = EX.BehaviorProceed
behavior_honk_and_wait = EX.BehaviorHonkAndWait
behavior_stop = EX.BehaviorStop
# behavior_slow_down = EX.BehaviorSlowDown
# behavior_speed_normal = EX.BehaviorSpeedNormal

# Predicates
requires_action = EX.requiresAction


# Add Subclass Relationships
graph.add((person, RDFS.subClassOf, living_being))
graph.add((animal, RDFS.subClassOf, living_being))
graph.add((bird, RDFS.subClassOf, animal))
graph.add((dog, RDFS.subClassOf, animal))
graph.add((cat, RDFS.subClassOf, animal))

graph.add((cardboard_box, RDFS.subClassOf, heavy_obstacle))
graph.add((bottle, RDFS.subClassOf, light_obstacle))
graph.add((plastic_bag, RDFS.subClassOf, light_obstacle))

# Behavior Relationships
graph.add((living_being, requires_action, behavior_honk_and_wait))
graph.add((light_obstacle, requires_action, behavior_proceed))
graph.add((heavy_obstacle, requires_action, behavior_avoid))

# Detected Instances
detected_person = EX.DetectedPerson
detected_bottle = EX.DetectedBottle
detected_box = EX.DetectedBox

graph.add((detected_person, RDF.type, person))
graph.add((detected_bottle, RDF.type, bottle))
graph.add((detected_box, RDF.type, cardboard_box))


graph.serialize(destination="./base_kg.ttl", format="turtle")
