# Strategy Visualization Documentation

This directory contains the design sources for the read-only strategy
visualization system.

## Reading Order

1. [Architecture and data contract](shared/architecture_and_data_contract.md)
   defines the product boundary and the visualization-ready result bundle.
2. [Backend design](backend/backend_design.md) defines exporter, storage,
   validation, catalog, API, security, and frontend handoff behavior.
3. [Frontend design status](frontend/README.md) identifies the stable inputs and
   remaining frontend-design deliverables.

## Structure

```text
strategy_visualization/
  README.md
  shared/
    architecture_and_data_contract.md
  backend/
    backend_design.md
  frontend/
    README.md
```

The shared contract is authoritative for data meaning. The backend design is
authoritative for publication and HTTP behavior. A future frontend design must
consume those public interfaces without importing Python internals or parsing
raw research artifacts.
