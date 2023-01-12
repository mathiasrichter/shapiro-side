from rdflib import Graph
from rdflib.plugins.sparql import prepareQuery
from rdflib import URIRef, BNode
from abc import ABC, abstractmethod
from pyspark.sql import SparkSession
from urllib.parse import urlparse
import re
from threading import Thread, Event
import os
from datetime import datetime

class SidecarThread(Thread):
    """
    Separate thread that does housekeeping on schemas. This is required
    to keep the server in sync with the schemas when the server runs
    for long times while schemas get added/removed in the file system.
    """

    def __init__(self, sleep_seconds, action):
        Thread.__init__(self)
        self.sleep_seconds = sleep_seconds
        self.last_execution_time = None
        self.stopped = Event()
        self.action = action

    def stop(self):
        self.stopped.set()

    def run(self):
        while not self.stopped.is_set():
            self.action()
            self.stopped.wait(self.sleep_seconds)
     
     
class Sidecar(ABC):
    """A Sidecar is the abstract superclass from which all sidecars descent.
    On this level, a sidecar takes the IRI of a semantic model defining the format for
    descriptions of the sidecar and it takes the IRI of the actual data describing
    the sidecar in a way compliant with the model.
    The Sidecar has an abstract method that subclasses need to implement as a notion of running this particular sidecar
    by interpreting the specified description (available the data IRI) in the context of the
    semantic model (available at the model IRI). 
    This class assumes a model as described at ./models/DataProduct.ttl"""
     
    DATA_PRODUCT_ANCHOR = '/DataProduct#'
    DATA_PRODUCT_SLASH = '/DataProduct/'
    NETLOC_SEP = '___'
     
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
        self.dptNamespace = None
        for n in self.graph.namespace_manager.namespaces():
            ns = str(n[1])
            if ns.endswith(self.DATA_PRODUCT_ANCHOR) or ns.endswith(self.DATA_PRODUCT_SLASH):
                self.dptNamespace = ns
        if self.dptNamespace is None:
            raise Exception("Could not identify namespace of model for DataProduct.")
        self.prepare_queries(self.dptNamespace)         
        
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
        self.INSTANCE_OF_CLASS_QUERY = prepareQuery(namespace_bindings + """
                SELECT DISTINCT ?instance
                WHERE { 
                    ?instance rdf:type ?leafClass . 
                    ?leafClass rdfs:subClassOf* ?class .
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
        instance = None
        if urlparse(instance_iri).scheme == '': # if there's no scheme it must be a plain node, not a uri reference
            instance = BNode(instance_iri)
        else:
            instance = URIRef(instance_iri)
        result = self.graph.query(self.PROPERTIES_OF_INSTANCE_QUERY, initBindings = { 'instance': instance })
        properties = {}
        for row in result:
            properties[row.property] = row.value
        return properties      
    
    def flatten(self, iri:str)->str:
        url = urlparse(iri)
        netloc = url.netloc
        path = url.path
        netloc = netloc.replace('.', '_')
        path = path.replace('/', '_')
        return netloc + self.NETLOC_SEP + path
    
    def unflatten(self, name:str)->str:
        s = name.split(self.NETLOC_SEP)
        if len(s) == 2:
            netloc = s[0].replace('_', '.')
            path = s[1].replace('_', '/')
            return netloc+path
        else:
            raise Exception("Could not unflatten '{}' - unrecognized format".format(name))
        
    @abstractmethod
    def start(self):
        """Performs sidecar actions by interpreting relevant parts of the
        data graph describing the actual data product associated with this sidecar instance.
        These actions can be one-off (so start finishes after performing all actions), or continuous
        (ie. start runs a loop or even spawns multiple threads for repeating and concurrent action). 
        In case of continuous action the sidecar can be stopped using the stop method.
        """
        pass
    
    @abstractmethod
    def stop(self):
        """Halts all activity of this sidecar (if it has previously been started and is in 
        some sort of a running state by whatever definition).
        """
        pass 
    
class SparkSidecar(Sidecar):
    """An abstract sidecar that uses Spark to process data.
    """
    
    def __init__(self, model_iri:str, data_iri:str, sparkSession:SparkSession):
        super().__init__(model_iri, data_iri)
        self.sparkSession = sparkSession
    
    def log_distribution(self, title:str, issued:datetime, accessService:str, accessUrl:str, conformsTo:str):
        entry = [{"http://www.w3.org/ns/dcat#title": title,
               "http://www.w3.org/ns/dcat#issued": issued,
               "http://www.w3.org/ns/dcat#accessService": accessService,
               "http://www.w3.org/ns/dcat#accessUrl": accessUrl,
               "http://www.w3.org/ns/dcat#conformsTo": conformsTo}]
        df = self.sparkSession.DataFrame(entry)
        df.write.mode("append").saveAsTable("http://www.w3.org/ns/dcat#Distribution")

class FileInputPortSidecar(SparkSidecar):
    """This sidecar implementation operates the file-based input port as declared in the desciption under data_iri 
    and shares this data via a SparkSession within the architecture quantum of the data product declared under data_iri."""
    
    MODEL_PROP              = "/hasDataModel"
    SCHEDULE_PROP           = "/schedule"
    PATH_PROP               = "http://www.w3.org/ns/dcat#endpointURL"   
    NAME_PATTERN_PROP       = "/namePattern"
    FORMAT_PROP             = "/format"
    FORMAT_CSV              = "/CSV"
    FORMAT_JSON             = "/JSON"
    UNIT_TYPE               = "https://www.w3.org/TR/owl-time/#unitType"
    UNIT_MINUTE             = "https://www.w3.org/TR/owl-time/#minutes"
    UNIT_SECOND             = "https://www.w3.org/TR/owl-time/#seconds"
    
    def __init__(self, model_iri:str, data_iri:str, port_iri:str, sparkSession:SparkSession):
        super().__init__(model_iri, data_iri, sparkSession)
        self.port_iri = port_iri
        self.configure()
        
    def configure(self):
        props = self.get_properties_of_instance(self.port_iri)
        self.configure_datamodel(props)
        self.configure_format(props)
        self.configure_name(props)
        self.configure_path(props)
        self.configure_schedule(props)
        self.executor = SidecarThread(self.schedule_interval, self.check_for_file)
        
    def configure_datamodel(self, properties:dict):
        self.datamodel = None
        for p in properties:
            if str(p).endswith(self.MODEL_PROP):
                self.datamodel = str(properties[p])
        if self.datamodel is None:
            raise Exception("No datamodel specified in properties for file input port {}.".format(self.port_iri))        
    
    def configure_format(self, properties:dict):
        self.format = None
        for p in properties:
            if str(p).endswith(self.FORMAT_PROP):
                if str(properties[p].endswith(self.FORMAT_CSV)):
                    self.format = self.FORMAT_CSV
                elif str(properties[p].endswith(self.FORMAT_JSON)):
                    self.format = self.FORMAT_JSON
                else:
                    raise Exception("Unknown file format: {}".format(str(p)))
        if self.format is None:
            raise Exception("No format specified in properties for file input port {}.".format(self.port_iri))        
            
    def configure_name(self, properties:dict):
        self.name_pattern = None
        for p in properties:
            if str(p).endswith(self.NAME_PATTERN_PROP):
                self.name_pattern = str(properties[p])
        if self.name_pattern is None:
            raise Exception("No name pattern specified in properties for file input port {}.".format(self.port_iri))                    

    def configure_path(self, properties:dict):
        self.path = None
        for p in properties:
            if str(p) == (self.PATH_PROP):
                path = str(properties[p])
                self.path = urlparse(path).path                
        if self.path is None:
            raise Exception("No path/endpointURL specified in properties for file input port {}.".format(self.port_iri))                    

    def configure_schedule(self, properties:dict):
        # currently assuming the general time description of the schedule represents a frequency
        # in some time unit (s,min)
        # TODO: find or create a more elaborate implementation of schedule to express more complex
        # schedules (e.g. on specific weekdays every 30 seconds, every month at the second Tuesday at 8 a.m., etc.)
        # based on owl-time
        self.schedule_unit = None
        self.schedule_interval = None
        for p in properties:
            if str(p).endswith(self.SCHEDULE_PROP):
                sched_prop = self.get_properties_of_instance(str(properties[p]))
                for sp in sched_prop:
                    if str(sp) == self.UNIT_TYPE:
                        self.schedule_unit = str(sched_prop[sp])
                    if str(sp) == self.UNIT_SECOND:
                        self.schedule_interval = float(sched_prop[sp]) # seconds
                    elif str(sp) == self.UNIT_MINUTE:
                        self.schedule_interval = 60 * float(sched_prop[sp]) # seconds
        if self.schedule_unit is None or self.schedule_interval is None:
            raise Exception("Schedule must be specified as time unit type minutes or seconds {}.".format(self.port_iri))
        
    def check_for_file(self):
        print("checking")
        for f in os.listdir(self.path):
            if os.path.isfile( self.path + '/' + f ):
                match = re.search(f, self.name_pattern)
                if match is not None:
                    self.process_file(f)
                    
    def process_file(self, file):
        # read file
        # quality check file
        # save metadata in table representing this file as an instance of a distribution of the data set associated with the file input port
        # save file data in table so it becomes accessible to the dataproduct inside the quantum
        self.log_distribution(file, datetime.now(), self.port_iri, "file://" + self.path + '/' + file, self.datamodel )

    def start(self):
        self.executor.start()        
    
    def stop(self):
        self.executor.stop()
