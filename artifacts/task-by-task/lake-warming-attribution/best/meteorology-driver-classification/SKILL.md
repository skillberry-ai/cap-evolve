---
name: meteorology-driver-classification
description: Classify environmental and meteorological variables into driver categories for attribution analysis. Use when you need to group multiple variables into meaningful factor categories.
license: MIT
---

# Driver Classification Guide

## Overview

When analyzing what drives changes in an environmental system, it is useful to group individual variables into broader categories based on their physical meaning.

## Common Driver Categories

### Heat
Variables related to thermal energy and radiation:
- Air temperature
- Shortwave radiation
- Longwave radiation
- Net radiation (shortwave + longwave)
- Surface temperature
- Humidity
- Cloud cover

### Flow
Variables related to water movement:
- Precipitation
- Inflow
- Outflow
- Streamflow
- Evaporation
- Runoff
- Groundwater flux

### Wind
Variables related to atmospheric circulation:
- Wind speed
- Wind direction
- Gust speed
- Atmospheric pressure

### Human
Variables related to anthropogenic activities:
- Developed area
- Agriculture area
- Impervious surface
- Population density
- Industrial output
- Land use change rate

## Derived Variables

Sometimes raw variables need to be combined before analysis:
```python
# Combine radiation components into net radiation
df['NetRadiation'] = df['Longwave'] + df['Shortwave']
```

## Grouping Strategy

1. Identify all available variables in your dataset
2. Assign each variable to a category based on physical meaning
3. Create derived variables if needed
4. Variables in the same category should be correlated

## Validation

After statistical grouping, verify that:
- Variables load on expected components
- Groupings make physical sense
- Categories are mutually exclusive

## Reporting the dominant driver

The whole point of classifying into categories is that the answer is expressed as a
**category**, not a raw variable. When asked for the most important driver of an outcome,
report the **category name** (e.g. `Heat`, `Flow`, `Wind`, `Human`) and that category's
aggregate contribution. Do this even when the request says "most important variable" or the
output column is named `variable` — a single measured column such as `AirTempLake` is the
wrong answer; the category it belongs to (`Heat`) is the right one. Attribute per category
with the contribution-analysis skill.

## Best Practices

- Use domain knowledge to define categories
- Combine related sub-variables before analysis
- Keep number of categories manageable (3-5 typically)
- Document your classification decisions
