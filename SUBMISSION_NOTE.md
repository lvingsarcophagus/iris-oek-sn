# Submission note — TASK 058 / IRIS-OEK-SN

The repository root contains the assignment implementation, Docker setup, tests,
mappings and validation evidence. The exact WFS endpoint returned HTTP 404 when
rechecked on 29 October 2026 (Europe/Vilnius), including the canonical capabilities
request without a version parameter. Headers and response checksums are recorded
under evidence/.

The submission therefore uses the **fixture-based WFS demonstrator expressly
permitted by the brief**. Discovery, schema inspection, controlled pagination,
normalization, geometry validation, projected staging loading and idempotence are
implemented and tested. Fixtures are explicitly synthetic; no other dataset is
substituted and no restricted service is bypassed.

Exact live-layer schema, permissions and registered cadastral/eco-account domain
membership remain unverified. Missing attributes are never guessed. All application
writes target isolated iris_staging resources; there are no iris_core or production
writes. README.md provides the clean-clone run/test commands; REQUIREMENTS_AUDIT.md
and QUALITY_REPORT.md explain evidence and remaining acceptance limits.
