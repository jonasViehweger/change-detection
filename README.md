# Monitoring Disturbances

This tool enables near real-time disturbance detection using a flavor of the Continuous Change Detection and Classification (CCDC) algorithm.
Processing is done using Sentinel Hub APIs which are available for free through the Copernicus Dataspace Ecosystem.

## Quick Start

### Installation

Install with pip from github:

```bash
pip install git+https://github.com/jonasViehweger/change-detection.git
```

then initialize a new monitor:

```python
import disturbancemonitor as dm
from datetime import date

geojson_aoi = { "type": "Feature",
       "geometry": {
         "type": "Polygon",
         "coordinates": [
           [ [100.0, 0.0], [101.0, 0.0], [101.0, 1.0],
             [100.0, 1.0], [100.0, 0.0] ]
           ]

       }
    }

monitor = dm.start_monitor(
   name="MyMonitor",
   monitoring_start=date.today(),
   geometry=geojson_aoi,
)
```

then use `monitor()` to monitor new acquisitions for changes:

```python
monitor.monitor()
```

or dump the model and reload at a later date

```python
monitor.dump()
# load from config by name
reloaded_monitor = dm.load_monitor(name="MyMonitor")
```
