from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery
from abc import ABC, abstractmethod
from pyspark.sql import SparkSession

class Sidecar(ABC):
    """A Sidecar is the abstract superclass from which all sidecars descent.
    On this level, a sidecar takes the IRI of a semantic model defining the format for
    descriptions of the sidecar and it takes the IRI of the actual data describing
    the sidecar in a way compliant with the model.
    The Sidecar has an abstract method that subclasses need to implement as a notion of running this particular sidecar
    by interpreting the specified description (available the data IRI) in the context of the
    semantic model (available at the model IRI). 
    This class assumes a model as described at ./models/DataProduct.ttl"""
    
    INPUT_PORT_QUERY = prepareQuery("""
            PREFIX dtp: <http://example.org/DataProduct/> 
            SELECT DISTINCT ?inputPort
            WHERE { 
                ?inputPortClass rdfs:subClassOf* dtp:InputPort. 
                ?inputPort rdf:type ?inputPortClass. 
            }
        """)
    
    OUTPUT_PORT_QUERY = prepareQuery("""
            PREFIX dtp: <http://example.org/DataProduct/>
            SELECT DISTINCT ?outputPort
            WHERE { 
                ?outputPortClass rdfs:subClassOf* dtp:OutputPort. 
                ?outputPort rdf:type ?outputPortClass. 
            }
        """)
    
    FILE_INPUT_PORT_QUERY = prepareQuery("""
            PREFIX dtp: <http://example.org/DataProduct/>
            SELECT DISTINCT ?inputPort
            WHERE { 
                ?inputPort rdf:type dtp:FileInputPort. 
            }
        """)                                         
    
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
        
    def get_instances_of(self, class_iri:str):
        pass
        
    def get_input_ports(self):
        result = self.graph.query(self.INPUT_PORT_QUERY)
        inputPorts = []
        for row in result:
            inputPorts.append(row.inputPort)
        return inputPorts
    
    def get_output_ports(self):
        result = self.graph.query(self.OUTPUT_PORT_QUERY)
        outputPorts = []
        for row in result:
            outputPorts.append(row.outputPort)
        return outputPorts
    
    def get_file_input_ports(self):
        result = self.graph.query(self.FILE_INPUT_PORT_QUERY)
        inputPorts = []
        for row in result:
            inputPorts.append(row.inputPort)
        return inputPorts

    @abstractmethod
    def run(self):
        """Performs sidecar actions by interpreting relevant parts of the
        data graph describing the actual data product associated with this sidecar instance.
        """
        pass
 
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
        pass
