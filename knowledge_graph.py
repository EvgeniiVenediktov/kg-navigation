import os
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS
from pyvis.network import Network
import networkx as nx

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
    behavior = kg.get_behavior_for_instance("DetectedPerson")
    print(f"Recommended behavior for DetectedPerson: {behavior}")
