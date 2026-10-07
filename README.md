# OrgLens

Independent portfolio prototype designed & developed by Phoebe Wang (2026).

OrgLens demonstrates an organizational-effectiveness and workforce-planning workflow using fully synthetic data. No World Bank Group or IFC employee data are used.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## No-code data updates

The durable demo inputs are in `data/`:
- `workforce.csv`
- `business_metrics.csv`
- `skill_demand.csv`
- `job_architecture.csv`

Edit a CSV in Excel, preserve the column names, and replace that file in GitHub. Streamlit will reload the repository and recalculate the app.

## Responsible use

Metrics are diagnostic signals for human review, not automated employment recommendations. Workload and skill-demand measures are fictional demonstration proxies.
