# API Reference

This page provides detailed documentation for all classes and functions in the Disturbance Monitor package.

## Core Functions

### start_monitor

::: disturbancemonitor.start_monitor

### load_monitor

::: disturbancemonitor.load_monitor

## Monitor Class

## Configuration Classes

### MonitorParams

::: disturbancemonitor.MonitorParameters

### GeoConfigHandler

::: disturbancemonitor.GeoConfigHandler

## Backend Classes

### Backend

::: disturbancemonitor.backends.Backend

## Examples

### Basic Monitoring Setup

```python
import disturbancemonitor as dm
from datetime import date, timedelta

# Create monitor
monitor = dm.start_monitor(
    name="example_monitor",
    monitoring_start=date.today() - timedelta(days=30),
    geometry={
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [-60.0, -3.0], [-59.9, -3.0],
                [-59.9, -2.9], [-60.0, -2.9],
                [-60.0, -3.0]
            ]]
        }
    }
)

# Run monitoring
results = monitor.monitor()
```

### Custom Configuration

```python
from disturbancemonitor import MonitorParams

# Custom parameters
params = MonitorParams(
    threshold=0.03,
    min_observations=15,
    bands=['B04', 'B08', 'B11'],
    cloud_threshold=0.2
)

monitor = dm.start_monitor(
    name="custom_monitor",
    monitoring_start=date(2024, 1, 1),
    geometry=geojson_geometry,
    params=params
)
```

### Working with Results

```python
# Get monitoring results
results = monitor.monitor()

# Access disturbances
for disturbance in results.disturbances:
    print(f"Date: {disturbance.date}")
    print(f"Confidence: {disturbance.confidence:.3f}")
    print(f"Location: {disturbance.geometry}")

# Export results
results.to_geojson("output.geojson")
results.to_csv("output.csv")

# Visualize
results.plot_time_series()
results.plot_map()
```

### Backend Management

```python
from disturbancemonitor.backends import SQLiteBackend

# Use custom backend
backend = SQLiteBackend(db_path="custom_monitors.db")
monitor = dm.start_monitor(
    name="db_monitor",
    monitoring_start=date.today(),
    geometry=geometry,
    backend=backend
)
```

## Error Handling

### Common Exceptions

```python
try:
    monitor = dm.start_monitor(
        name="test_monitor",
        monitoring_start=date.today(),
        geometry=invalid_geometry
    )
except ValueError as e:
    print(f"Invalid geometry: {e}")

try:
    results = monitor.monitor()
except ConnectionError as e:
    print(f"API connection failed: {e}")
```

### Validation

```python
from disturbancemonitor.geo_config_handler import GeoConfigHandler

# Validate geometry
handler = GeoConfigHandler()
is_valid = handler.validate_geometry(geojson_geometry)

if not is_valid:
    print("Invalid geometry provided")
```

## Configuration Files

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `COPERNICUS_USERNAME` | Copernicus Dataspace username | Yes |
| `COPERNICUS_PASSWORD` | Copernicus Dataspace password | Yes |
| `DM_CACHE_DIR` | Cache directory for data | No |
| `DM_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No |

### Configuration File Format

```toml
# config.toml
[monitor.default]
threshold = 0.05
min_observations = 12
bands = ["B04", "B08", "B11", "B12"]

[api]
base_url = "https://sh.dataspace.copernicus.eu"
timeout = 30

[cache]
enabled = true
max_size = "1GB"
ttl = 3600
```

## Performance Tips

### Optimization Strategies

1. **Area Size**: Keep areas under 100 km² for optimal performance
2. **Date Range**: Limit monitoring periods to reduce processing time
3. **Band Selection**: Use only necessary bands to reduce data transfer
4. **Caching**: Enable caching for repeated queries
5. **Parallel Processing**: Use multiple monitors for large areas

### Memory Management

```python
# For large areas, use tiling
from disturbancemonitor.utils import tile_geometry

tiles = tile_geometry(large_geometry, tile_size=0.1)  # 0.1 degree tiles

monitors = []
for i, tile in enumerate(tiles):
    monitor = dm.start_monitor(
        name=f"tile_{i}",
        monitoring_start=start_date,
        geometry=tile
    )
    monitors.append(monitor)
```

## Changelog

### Version 0.1.0
- Initial release
- Basic CCDC implementation
- Sentinel Hub integration
- SQLite backend support
