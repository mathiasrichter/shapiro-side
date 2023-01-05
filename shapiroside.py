from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery
from rdflib import URIRef
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
        namespace_bindings = """
                PREFIX dtp: <""" + dataProductNamespace + """> 
                PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
                PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
                PREFIX owl: <http://www.w3.org/2002/07/owl#>
        """
        self.INPUT_PORT_QUERY = prepareQuery(namespace_bindings + """
                SELECT DISTINCT ?inputPort
                WHERE { 
                    ?inputPortClass rdfs:subClassOf* dtp:InputPort. 
                    ?inputPort rdf:type ?inputPortClass. 
                }
            """)        
        self.OUTPUT_PORT_QUERY = prepareQuery(namespace_bindings + """
                SELECT DISTINCT ?outputPort
                WHERE { 
                    ?outputPortClass rdfs:subClassOf* dtp:OutputPort. 
                    ?outputPort rdf:type ?outputPortClass . 
                }
            """)                               
        self.INSTANCE_OF_CLASS_QUERY = prepareQuery(namespace_bindings + """
                SELECT DISTINCT ?instance
                WHERE { 
                    ?instance rdf:type ?class. 
                }
            """)                                              
        self.PROPERTIES_OF_INSTANCE_QUERY = prepareQuery(namespace_bindings + """
                SELECT DISTINCT ?property ?value
                WHERE { 
                    ?instance ?property ?value .
                }
            """)                                      

    def get_instances_of_class(self, class_iri:str):
        result = self.graph.query(self.INSTANCE_OF_CLASS_QUERY, initBindings = { 'class': URIRef(class_iri) })
        instances = []
        for row in result:
            instances.append(row.instance)
        return instances
    
    def get_properties_of_instance(self, instance_iri:str):
        result = self.graph.query(self.PROPERTIES_OF_INSTANCE_QUERY, initBindings = { 'instance': URIRef(instance_iri) })
        properties = {}
        for row in result:
            properties[row.property] = row.value
        return properties        
        
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
