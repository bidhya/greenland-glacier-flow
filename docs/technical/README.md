# Technical Documentation Index

This folder contains detailed technical documentation for the Greenland Glacier Flow Processing project.

## Processing Optimizations

- **[Sentinel-2 Processing Optimizations](sentinel2_optimizations.md)** (October 2025)
  - 50%+ reduction in unnecessary downloads
  - Tile filtering and centralized download location
  - AWS Lambda memory constraints and platform recommendations

## Quality Control

- **[Landsat Coverage Quality Control](landsat_coverage_control.md)** (December 2025)
  - 50% minimum glacier coverage threshold
  - Pixel size calculations (225 m² for 15m × 15m Landsat resolution)
  - Scene-level rejection for low-coverage data

## Configuration Management

- **[Sentinel-2 Folder Structure Automation](folder_structure_automation.md)** (December 2025)
  - Parameterized folder structure selection (`--folder_structure {old|new}`)
  - Elimination of manual comment/uncomment operations
  - Backward compatible with existing workflows

## Related Documentation

- **[AGENTS.md](../AGENTS.md)** - AI agent quick reference and high-level architecture
- **[CHANGELOG.md](../CHANGELOG.md)** - Summary of all changes and implementations
- **[README.md](../README.md)** - Project overview and setup instructions