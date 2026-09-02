# TransitPulse dbt Project

This dbt project will transform raw GTFS static tables and GTFS-RT snapshot tables into staging, intermediate, and mart models.

Model layers:

- `models/staging/`: source-aligned cleanup and type normalization.
- `models/intermediate/`: reusable joins and business logic.
- `models/marts/`: analytics-ready tables for reporting and portfolio analysis.

Run dbt from the repository root:

```powershell
dbt debug --project-dir dbt --profiles-dir dbt
dbt run --project-dir dbt --profiles-dir dbt
dbt test --project-dir dbt --profiles-dir dbt
```
