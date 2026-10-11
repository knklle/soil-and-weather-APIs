# Soil and Weather API Integration App

This project is a Streamlit-based application developed for **ITD112 Laboratory Exercise 1**.  
It integrates data from two public APIs — **SoilGrids 2.0** and **Open-Meteo Historical Weather API** — and combines them into one analysis workflow for selected locations in Mindanao.

The application demonstrates the full API integration process: defining inputs, building requests, sending API calls safely, parsing JSON responses, converting units, joining datasets, analyzing the integrated data, visualizing results, and exporting final datasets.

---

## Project Overview

The app collects two different kinds of environmental data:

- **Static soil properties** from SoilGrids
- **Daily historical weather data** from Open-Meteo

These datasets are connected using the selected site name and coordinates.

The final result is an integrated dataset where each daily weather record also contains the corresponding soil properties for that location.

---

## Data Sources

### SoilGrids 2.0 — ISRIC

SoilGrids provides modelled soil information for a selected latitude and longitude.

The application retrieves the following soil properties at the **0–5 cm depth**:

- Clay
- Sand
- Silt
- Soil pH (`phh2o`)
- Soil Organic Carbon (`soc`)

SoilGrids returns mapped values, so each property is converted using its own `d_factor` before analysis.

Example:

```text
Converted value = raw mean / d_factor
