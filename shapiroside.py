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
     
    def __init__(self, model_iri:str, data_iri:str):
        """Initialize this sidecar.

        Args:
            model_iri (str): An IRI pointing to a semantic model defining the format that the data graph must have.
            data_iri (str): An II pointing to the actual description of a data product in compliance with the model.
            The model needs to define the description for data products in a namespace ending with "/DataProduct/" or "/DataProduct#".
        """
        self.model_iri = model_iri
        self.data_iri = data_iri
        self.graph = Graph().parse(model_iri)
        self.graph.parse(self.data_iri) # merge all into the same graph
        dptNamespace = None
        for n in self.graph.namespace_manager.namespaces():
            ns = str(n[1])
            if ns.endswith("/DataProduct/") or ns.endswith("/DataProduct#"):
                dptNamespace = ns
        if dptNamespace is None:
            raise Exception("Could not identify namespace of model for DataProduct.")
        self.prepare_queries(dptNamespace)               
        
    def prepare_queries(self, dataProductNamespace:str):
        """Prepare all SPARQL queries needed to interpret the dataproduct description.
        
        Args:
            dataProductNamespace (str): The namespace within which the model of the dataproduct description is defined.
        """
        self.INPUT_PORT_QUERY = prepareQuery("""
                PREFIX dtp: <""" + dataProductNamespace + """> 
                SELECT DISTINCT ?inputPort
                WHERE { 
                    ?inputPortClass rdfs:subClassOf* dtp:InputPort. 
                    ?inputPort rdf:type ?inputPortClass. 
                }
            """)        
        self.OUTPUT_PORT_QUERY = prepareQuery("""
                PREFIX dtp: <""" + dataProductNamespace + """> 
                SELECT DISTINCT ?outputPort
                WHERE { 
                    ?outputPortClass rdfs:subClassOf* dtp:OutputPort. 
                    ?outputPort rdf:type ?outputPortClass. 
                }
            """)       
        self.FILE_INPUT_PORT_QUERY = prepareQuery("""
                PREFIX dtp: <""" + dataProductNamespace + """> 
                SELECT DISTINCT ?inputPort
                WHERE { 
                    ?inputPort rdf:type dtp:FileInputPort. 
                }
            """)                                      
        
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
