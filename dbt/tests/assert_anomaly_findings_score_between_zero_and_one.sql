select
    anomaly_id,
    anomaly_score
from {{ ref('fct_anomaly_findings') }}
where anomaly_score < 0.0
    or anomaly_score > 1.0
