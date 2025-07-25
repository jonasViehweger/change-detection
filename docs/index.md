---
template: home.html
hide:
  - navigation
  - toc
  - title
---

<div class="hero-wrapper">
  <div class="hero-section">
    <div class="hero-content">
      <h1>Disturbance Monitor</h1>
      <h2>Near Real-Time Land Use Change Detection</h2>
      <p>Monitor land disturbances using satellite imagery and the power of Continuous Change Detection and Classification (CCDC) algorithm. Get alerted to deforestation, and other changes as they happen.</p>
      <div class="hero-buttons">
        <a href="getting-started/" class="md-button md-button--primary">
          Get Started
        </a>
        <a href="https://github.com/jonasViehweger/change-detection" class="md-button">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="20" height="20"><path fill="currentColor" d="M12 2A10 10 0 0 0 2 12C2 16.42 4.87 20.17 8.84 21.5C9.34 21.58 9.5 21.27 9.5 21C9.5 20.77 9.5 20.14 9.5 19.31C6.73 19.91 6.14 17.97 6.14 17.97C5.68 16.81 5.03 16.5 5.03 16.5C4.12 15.88 5.1 15.9 5.1 15.9C6.1 15.97 6.63 16.93 6.63 16.93C7.5 18.45 8.97 18 9.54 17.76C9.63 17.11 9.89 16.67 10.17 16.42C7.95 16.17 5.62 15.31 5.62 11.5C5.62 10.39 6 9.5 6.65 8.79C6.55 8.54 6.2 7.5 6.75 6.15C6.75 6.15 7.59 5.88 9.5 7.17C10.29 6.95 11.15 6.84 12 6.84C12.85 6.84 13.71 6.95 14.5 7.17C16.41 5.88 17.25 6.15 17.25 6.15C17.8 7.5 17.45 8.54 17.35 8.79C18 9.5 18.38 10.39 18.38 11.5C18.38 15.32 16.04 16.16 13.81 16.41C14.17 16.72 14.5 17.33 14.5 18.26C14.5 19.6 14.5 20.68 14.5 21C14.5 21.27 14.66 21.59 15.17 21.5C19.14 20.16 22 16.42 22 12A10 10 0 0 0 12 2Z"/></svg>
          View on GitHub
        </a>
      </div>
    </div>
    <div class="hero-image">
      <div class="mermaid">
        graph LR
            A[🛰️ Satellite Data] --> B[📊 Time Series Analysis]
            B --> C[🔍 Change Detection]
            C --> D[🚨 Disturbance Alert]

            style A fill:#e1f5fe
            style B fill:#f3e5f5
            style C fill:#fff3e0
            style D fill:#ffebee
      </div>
    </div>
  </div>
</div>

## Key Features

<div class="grid cards" markdown="1">

- :material-satellite-variant: **Satellite-Powered**

    ---

    Leverages Sentinel Hub APIs through the Copernicus Dataspace Ecosystem for comprehensive Earth observation data.

- :material-clock-fast: **Near Real-Time**

    ---

    Detect disturbances as they happen with automated monitoring of new satellite acquisitions.

- :material-brain: **CCDC Algorithm**

    ---

    Uses proven Continuous Change Detection and Classification methodology for accurate results.

- :material-api: **Easy Integration**

    ---

    Simple Python API that integrates seamlessly into your existing workflows and systems.

</div>

## Quick Example

```python
import disturbancemonitor as dm
from datetime import date

# Define your area of interest
geojson_aoi = {
    "type": "Feature",
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[100.0, 0.0], [101.0, 0.0], [101.0, 1.0], [100.0, 1.0], [100.0, 0.0]]]
    }
}

# Start monitoring
monitor = dm.start_monitor(
    name="ForestWatch",
    monitoring_start=date.today(),
    geometry=geojson_aoi,
)

# Check for new disturbances
monitor.monitor()
```

## Use Cases

- **Forest Conservation**: Monitor protected areas for illegal logging and deforestation
- **Fire Detection**: Early warning systems for wildfire management
- **Agricultural Monitoring**: Track crop health and harvest patterns
- **Urban Planning**: Monitor urban expansion and land use changes
- **Environmental Research**: Study ecosystem changes over time

---

<div class="cta-section" markdown="1">

### Ready to Start Monitoring?

[Install Now :material-download:](getting-started.md){ .md-button .md-button--primary .md-button--large }

</div>

<style>

/* Application header should be static for the landing page */
.md-header {
    position: initial;
}

/* Remove spacing, as we cannot hide it completely */
.md-main__inner {
    margin-top: 0;
}

.md-content__inner {
    padding: 0;
}

.md-content__inner:before {
    content: none;
}

.md-main
.hero-wrapper {
    position: relative;
    margin-left: calc(-50vw + 50%);
    margin-right: calc(-50vw + 50%);
    margin-top: 0;
    width: 100vw;
    background: linear-gradient(135deg, #e8f5e8 0%, #f0f8ff 100%);
    padding: 4rem 0;
}

/* Dark mode support for hero */
[data-md-color-scheme="slate"] .hero-wrapper {
    background: linear-gradient(135deg, #1a2332 0%, #2d3748 100%);
}

.hero-section {
    display: flex;
    align-items: center;
    gap: 3rem;
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 2rem;
}

.hero-content {
    flex: 1;
}

.hero-content h1 {
    font-size: 3rem;
    font-weight: bold;
    margin-bottom: 0.5rem;
    color: var(--md-primary-fg-color);
}

.hero-content h2 {
    font-size: 1.5rem;
    font-weight: 400;
    margin-bottom: 1rem;
    color: var(--md-default-fg-color--light);
}

.hero-content p {
    font-size: 1.1rem;
    line-height: 1.6;
    margin-bottom: 2rem;
    color: var(--md-default-fg-color);
}

.hero-buttons {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
}

.hero-buttons .md-button {
    padding: 0.75rem 1.5rem;
    font-size: 1rem;
    text-decoration: none;
    border-radius: 4px;
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
}

.hero-image {
    flex: 1;
    text-align: center;
}

.cta-section {
    text-align: center;
    margin: 3rem 0;
    padding: 2rem;
    background-color: var(--md-primary-fg-color--light);
    border-radius: 8px;
}

@media (max-width: 768px) {
    .hero-section {
        flex-direction: column;
        text-align: center;
        padding: 0 1rem;
    }

    .hero-content h1 {
        font-size: 2rem;
    }

    .hero-content h2 {
        font-size: 1.2rem;
    }

    .hero-wrapper {
        padding: 2rem 0;
    }

    .hero-buttons {
        justify-content: center;
    }
}
</style>
