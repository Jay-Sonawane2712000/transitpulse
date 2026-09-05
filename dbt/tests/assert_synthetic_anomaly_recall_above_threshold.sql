select
    metric_scope,
    anomaly_type,
    recall
from {{ ref('int_anomaly_detection_metrics') }}
where metric_scope = 'overall'
    and anomaly_type = 'all_anomalies'
    and (
        recall is null
        or recall < 0.90
    )
