import os
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS
from pyvis.network import Network
import networkx as nx
from typing import List

class KG:
    def __init__(self, path: str="./base_kg.ttl", format: str="turtle") -> None:
        self.graph = Graph()
        self.path = path
        self.format = format
        self.EX = Namespace("http://my-robotic-vision-kg.org/")
        if os.path.exists(path):
            self.graph.parse(path, format=format)
        else:
            raise FileNotFoundError(f"Knowledge graph file not found at {path}")
        
    def save(self, path: str=None, format: str=None) -> None:
        file_path = path if path else "altered_kg.ttl"
        file_format = format if format else self.format
        self.graph.serialize(destination=file_path, format=file_format)

    def get_behavior_for_instance(self, instance: str) -> str:
        q = """SELECT ?behavior 
                WHERE { 
                    ex:%s a ?type . 
                    ?type rdfs:subClassOf* ?parentClass .
                    ?parentClass ex:requiresAction ?behavior .
                }"""% instance
                
        results = self.graph.query(q, initNs={"ex": self.EX, "rdfs": RDFS})
        for row in results:
            return row.behavior.split("/")[-1]

    def get_instances_sorted_by_importance(self, instances: List[str]) -> List[str]:
        """
        Sort detected instances from least to most important based on the
        ex:moreImportantThan hierarchy defined in the knowledge graph.
        """
        if not instances:
            return []

        # Fetch importance edges once
        importance_query = """
            SELECT ?more ?less
            WHERE { ?more ex:moreImportantThan ?less . }
        """
        edges = [
            (str(row.more), str(row.less))
            for row in self.graph.query(importance_query, initNs={"ex": self.EX})
        ]

        # Build adjacency and compute depths (0 = most important)
        children = {}
        indegree = {}
        for parent, child in edges:
            children.setdefault(parent, []).append(child)
            indegree[child] = indegree.get(child, 0) + 1
            indegree.setdefault(parent, 0)

        depths = {}
        def dfs(node: str, depth: int) -> None:
            depths[node] = max(depths.get(node, -1), depth)
            for nxt in children.get(node, []):
                dfs(nxt, depth + 1)

        roots = [n for n, deg in indegree.items() if deg == 0]
        for root in roots:
            dfs(root, 0)

        def score_for_instance(inst: str) -> int:
            # Find all ancestor classes for the instance that participate
            q = """SELECT ?cls
                   WHERE {
                       ex:%s a ?type .
                       ?type rdfs:subClassOf* ?cls .
                   }""" % inst
            classes = [
                str(row.cls)
                for row in self.graph.query(q, initNs={"ex": self.EX, "rdfs": RDFS})
            ]
            scores = [depths[c] for c in classes if c in depths]
            # Larger depth => less important; fallback to max depth + 1
            return max(scores) if scores else max(depths.values(), default=0) + 1

        ranked = sorted(instances, key=lambda inst: score_for_instance(inst), reverse=True)
        return ranked
    
    def visualize(self, output_html: str="kg_visualization.html") -> None:
        net = Network(notebook=False, height="1080px", width="100%", directed=True, bgcolor="#FFFFFF", font_color="#000000")


        for s, p, o in self.graph:
            s_name = str(s).split('/')[-1].split('#')[-1]
            p_name = str(p).split('/')[-1].split('#')[-1]
            o_name = str(o).split('/')[-1].split('#')[-1]
            print(f"{s_name} -- {p_name} --> {o_name}")


            if p == RDF.type:
                net.add_node(s_name, label=s_name, color='#00bfff', size=25) # Detected instances
            else:
                net.add_node(s_name, label=s_name, color="#d10c0f", size=25) # Classes
        
            if p == self.EX.requiresAction:
                net.add_node(o_name, label=o_name, color='#0BC76F', size=25) # Behaviors
            else:
                net.add_node(o_name, label=o_name, color='#d10c0f', size=25) # Classes

            net.add_edge(s_name, o_name, label=p_name, title=p_name, color="#000000")

        net.repulsion(spring_length=110, node_distance=120)


        # net.show_buttons(filter_=['physics'])
        net.save_graph(output_html)
        

if __name__ == "__main__":
    kg = KG()
    # kg.visualize()
    behavior = kg.get_behavior_for_instance("DetectedPlasticBag")
    print(f"Recommended behavior for DetectedPlasticBag: {behavior}")
