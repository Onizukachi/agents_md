# PAPI v3 docs

The rules for writing PAPI v3 route and contract documentation live in the repository itself: `docs/papi/v3/README.md`. Read it there; this file intentionally holds no copy.

Run the documentation tooling in the Rails container, for example:

```bash
docker exec lt.rails bash -lc 'ruby script/api_docs.rb validate-sequential'
```

Other commands (`compile-controller`, `compile-openapi`, `report-sequential`) are listed in that README.
