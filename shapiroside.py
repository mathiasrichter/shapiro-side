from rdflib import Graph
from abc import ABC, abstractmethod
from pyspark.sql import SparkSession

class Sidecar(ABC):
    """A Sidecar is the abstract superclass from which all sidecars descent.
    On this level, a sidecar takes the IRI of a semantic model defining the format for
    descriptions of the sidecar and it takes the IRI of the actual data describing
    the sidecar in a way compliant with the model.
    The Sidecar has an abstract method that subclasses need to implement as a notion of running this particular sidecar
    by interpreting the specified description (available the data IRI) in the context of the
    semantic model (available at the model IRI)."""
    
    def __init__(self, model_iri:str, data_iri:str):
        """Initialize this sidecar.

        Args:
            model_iri (_type_): An IRI pointing to a semantic model defining the format that the data graph must have.
            data_iri (_type_): An II pointing to the actual description of a data product in compliance with the model.
        """
        self.model_iri = model_iri
        self.data_iri = data_iri
        self.graph = Graph().parse(model_iri)
        self.graph.parse(self.data_iri) # merge all into the same graph
        
    @abstractmethod
    def run(self):
        """Performs sidecar actions by interpreting relevant parts of the
        data graph describing the actual data product associated with this sidecar instance.
        """
        pass

class DataProduct(Sidecar):
    """A sidecar representing providing all information about a data product following the conceptual model described under
    ./models/DataProduct.ttl"""
    
    def __init__(self, model_iri:str, data_iri:str):
        """Initialize this sidecar.

        Args:
            model_iri (_type_): An IRI pointing to a semantic model defining the format that the data graph must have.
            data_iri (_type_): An IRI pointing to the actual description of a data product in compliance with the model.
        """
        super().__init__(model_iri, data_iri)
    
    def get_input_ports(self):
        query = """
            SELECT DISTINCT ?inputPort
            WHERE { 
                ?inputPortClass rdfs:subClassOf* dtp:InputPort. 
                ?inputPort rdf:type ?inputPortClass. 
            }
        """
        result = self.graph.query(query)
        inputPorts = []
        for row in result:
            inputPorts.append(row.inputPort)
        return inputPorts
    
    def get_output_ports(self):
        query = """
            SELECT DISTINCT ?inputPort
            WHERE { 
                ?inputPortClass rdfs:subClassOf* dtp:OutputPort. 
                ?inputPort rdf:type ?inputPortClass. 
            }
        """
        result = self.graph.query(query)
        inputPorts = []
        for row in result:
            inputPorts.append(row.inputPort)
        return inputPorts
    
    def get_file_input_ports(self):
        query = """
            SELECT DISTINCT ?inputPort
            WHERE { 
                ?inputPort rdf:type dtp:FileInputPort. 
            }
        """
        result = self.graph.query(query)
        inputPorts = []
        for row in result:
            inputPorts.append(row.inputPort)
        return inputPorts
    
    def run(self):
        print(self.get_input_ports())
        print(self.get_output_ports())
        print(self.get_file_input_ports())
 
class SparkSidecar(Sidecar):
    """An abstract sidecar that uses Spark to process data.
    """
    
    def __init__(self, model_iri:str, data_iri:str, sparkSession:SparkSession):
        super().__init__(model_iri, data_iri)
        self.sparkSession = sparkSession


class FileInputPort(SparkSidecar):
    """This sidecar implementation operates a file-based input port."""
    
    def __init__(self, model_iri:str, data_iri:str, sparkSession:SparkSession):
        super().__init__(model_iri, data_iri, sparkSession)
        
    def run(self):
        fileinputs_query = """
        SELECT DISTINCT ?p ?i ?v ?d
        WHERE {
            ?p dtp:hasInputPort ?i .
            ?i rdf:type dtp:FileInputPort .
            ?i ?v ?d .
        }"""

        qres = self.data.query(fileinputs_query)
        for row in qres:
            print(f"{row.p} has file input port {row.i} has attribute {row.v} with value {row.d}")   


