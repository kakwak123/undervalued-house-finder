# QA_LOG.md

Managed by the **QA Agent**. Tracks test results, open bugs, and regression history.
Bug IDs are cross-referenced in `BACKLOG.md` under the relevant item's Notes field.

---

## Bug Template

```
### BUG-NNN — Title
- **Date:** YYYY-MM-DD
- **Status:** Open | Fixed | Wont Fix
- **Linked Item:** BACKLOG item ID
- **Severity:** Critical | High | Medium | Low
- **Description:** What is broken and how to reproduce it.
- **Fix:** What was done to resolve it (fill in when Fixed).
```

---

## Test Coverage by Milestone

| Milestone | Item                            | Tests Exist | Status      | Notes                         |
| --------- | ------------------------------- | ----------- | ----------- | ----------------------------- |
| M1-2      | Core listing data model         | Yes         | Passing     | `models/tests/test_models.py` |
| M1-3      | Event timeline system           | Yes         | Passing     | Covered in `test_models.py`   |
| M1-4      | Listing ingestion pipeline      | No          | Not tested  | No automated tests yet        |
| M2-1      | Baseline price model            | No          | Not started | —                             |
| M2-2      | Price comparison                | No          | Not started | —                             |
| M2-3      | Undervaluation threshold        | No          | Not started | —                             |
| M3-1      | Auction cancellation signal     | No          | Not started | —                             |
| M3-2      | Re-auction detection            | No          | Not started | —                             |
| M3-3      | Compound signal (voided + drop) | No          | Not started | —                             |
| M3-4      | Opportunity scoring engine      | No          | Not started | —                             |
| S-1       | Scraper scheduler               | No          | Not started | —                             |
| S-2       | Scrape-to-ingest pipeline       | No          | Not started | —                             |
| S-3       | Rate limiting + retry           | No          | Not started | —                             |

---

## Open Bugs

_None logged yet._

---

## Resolved Bugs

_None resolved yet._

---

## QA Notes

- Run model tests: `cd models && poetry run pytest tests/ -v`
- No tests exist yet for the `ingestion/` package — first QA pass should establish a baseline test suite there
- Normalizer edge cases to watch: price extraction from description (regex-based, fragile), land size parsing with units like `m²`
