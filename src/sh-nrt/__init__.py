
from contextlib import suppress
import json

import boto3

from . import storage

class DisturbanceMonitor():
    def __init__(self, monitor_name):

        self._Name = name
        #store data

    @classmethod
    def create(cls, 
               name, 
               bucket_name,
               monitoring_start,
            geometry, 
            res, 
            datasource, harmonics=2, inputs=["NDVI"], metric="RMSE", sensitivity=5, boundary=5):

        storage = storage.Storage(name, bucket_name, backend="S3")
        storage.create(models, metrics)
        
        compute = Compute(monitoring_start, geometry, res, datasource, inputs)
        models = compute.models(harmonics)
        metrics = compute.metric(metric)

        storage.write_dataset(models, metrics)

        return cls(newName, s)
    
    def monitor(self):
        self.storage.get()
    
    # create
    # name, harmonics, inputs (NDVI?), metric, sensitivity, boundary 

    # load
    # name

    # delete
    # name

    # monitor

    # inspect
    # point