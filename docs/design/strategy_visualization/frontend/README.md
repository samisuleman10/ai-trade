# Strategy Visualization Frontend Design

**Status:** Ready for detailed design; frontend design is not yet complete.

The frontend must be designed against:

- [The shared architecture and data contract](../shared/architecture_and_data_contract.md)
- [The backend API and handoff specification](../backend/backend_design.md)

Before frontend implementation begins, the backend must publish the handoff
artifacts listed in backend design section 20:

- OpenAPI 3.1 snapshot
- Version 1 JSON Schemas
- Historical and shadow fixtures
- Catalog and error-response fixtures

The detailed frontend design should be added to this directory as
`frontend_design.md` and freeze:

- routes and page information architecture;
- component hierarchy and ownership;
- TypeScript types and API-client boundary;
- query caching, conditional polling, and URL state;
- chart-series, marker, stop, and target mappings;
- run, timeframe, overlay, sizing-variant, and trade selection behavior;
- loading, empty, stale, unsupported-version, and error states;
- responsive layouts and design tokens;
- keyboard, screen-reader, and contrast requirements;
- unit, component, accessibility, and end-to-end acceptance tests.

No frontend calculation may replace or reinterpret producer-generated
financial results.
