# Getting Started

Welcome to Disturbance Monitor! This guide will help you set up and start monitoring disturbances in satellite time series data.

## Installation

### Prerequisites

- Python 3.12 or higher
- A Copernicus Dataspace Ecosystem account (free)

### Install from GitHub

```bash
pip install git+https://github.com/jonasViehweger/change-detection.git
```

### Development Installation

If you want to contribute or modify the code:

```bash
git clone https://github.com/jonasViehweger/change-detection.git
cd change-detection
pip install -e .
```

## Setup

### Copernicus Dataspace Ecosystem

1. Create a free account at [Copernicus Dataspace Ecosystem](https://dataspace.copernicus.eu/)
2. Note your credentials for API access
3. Set up authentication (see Authentication section below)

### Authentication

Create a `.env` file in your project directory or set environment variables:

```bash
# .env file
COPERNICUS_USERNAME=your_username
COPERNICUS_PASSWORD=your_password
```

Or export them directly:

```bash
export COPERNICUS_USERNAME="your_username"
export COPERNICUS_PASSWORD="your_password"
```

## Basic Usage

### 1. Define Your Area of Interest

Create a GeoJSON polygon for the area you want to monitor:

```python
import disturbancemonitor as dm
from datetime import date

# Example: Small area in the Amazon
geojson_aoi = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[
            [-60.0, -3.0],  # West, South
            [-59.9, -3.0],  # East, South
            [-59.9, -2.9],  # East, North
            [-60.0, -2.9],  # West, North
            [-60.0, -3.0]   # Close polygon
        ]]
    }
}
```

### 2. Initialize a Monitor

```python
monitor = dm.start_monitor(
    name="AmazonWatch",
    monitoring_start=date(2024, 1, 1),
    geometry=geojson_aoi,
)
```

### 3. Run Monitoring

```python
# Check for new disturbances
results = monitor.monitor()

# Check results
if results.disturbances_detected:
    print(f"Found {len(results.disturbances)} disturbances!")
    for disturbance in results.disturbances:
        print(f"Date: {disturbance.date}, Confidence: {disturbance.confidence}")
```

### 4. Save and Load Monitors

```python
# Save monitor configuration
monitor.dump()

# Later, reload the monitor
reloaded_monitor = dm.load_monitor(name="AmazonWatch")
```

## Configuration Options

### Monitor Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `name` | str | Unique identifier for the monitor | Required |
| `monitoring_start` | date | Start date for monitoring | Required |
| `geometry` | dict | GeoJSON geometry of area to monitor | Required |
| `threshold` | float | Change detection sensitivity | 0.05 |
| `min_observations` | int | Minimum observations before detection | 12 |

### Advanced Configuration

```python
monitor = dm.start_monitor(
    name="CustomMonitor",
    monitoring_start=date(2024, 1, 1),
    geometry=geojson_aoi,
    threshold=0.03,  # More sensitive
    min_observations=20,  # More stable baseline
    bands=['B04', 'B08', 'B11'],  # Custom band selection
)
```

## Understanding Results

### Disturbance Object

Each detected disturbance contains:

- `date`: When the disturbance was detected
- `confidence`: Confidence score (0-1)
- `magnitude`: Change magnitude
- `geometry`: Spatial extent of the disturbance
- `metadata`: Additional information

### Result Visualization

```python
# Plot results
results.plot_time_series()
results.plot_disturbances_map()

# Export results
results.to_geojson("disturbances.geojson")
results.to_csv("disturbances.csv")
```

## Common Use Cases

### Forest Monitoring

```python
# Monitor a forest reserve
forest_monitor = dm.start_monitor(
    name="ForestReserve",
    monitoring_start=date(2024, 1, 1),
    geometry=forest_geojson,
    threshold=0.02,  # Sensitive to small changes
)
```

### Fire Detection

```python
# Quick fire detection
fire_monitor = dm.start_monitor(
    name="FireWatch",
    monitoring_start=date.today() - timedelta(days=30),
    geometry=fire_prone_area,
    bands=['B12', 'B11', 'B04'],  # Good for fire detection
)
```

### Urban Expansion

```python
# Monitor urban growth
urban_monitor = dm.start_monitor(
    name="CityGrowth",
    monitoring_start=date(2023, 1, 1),
    geometry=city_boundary,
    threshold=0.1,  # Less sensitive for gradual changes
)
```

## Troubleshooting

### Common Issues

**Authentication Errors**
```
Error: Invalid credentials
```
- Check your Copernicus Dataspace credentials
- Ensure environment variables are set correctly

**No Data Available**
```
Warning: No satellite data found for the specified period
```
- Check if your area of interest has satellite coverage
- Verify the date range is reasonable
- Ensure geometry is valid GeoJSON

**Memory Issues**
```
MemoryError: Unable to allocate array
```
- Reduce the size of your area of interest
- Increase the monitoring period to reduce data density

### Getting Help

- Check the [Reference](reference.md) documentation
- File issues on [GitHub](https://github.com/jonasViehweger/change-detection/issues)
- Review example notebooks in the repository

## Next Steps

- Explore the [Reference](reference.md) for detailed API documentation
- Check out example notebooks in the repository
- Set up automated monitoring with scheduling tools
- Integrate with alerting systems for real-time notifications
