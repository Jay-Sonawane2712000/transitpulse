{{ config(materialized='table') }}

with predictions as (

    select *
    from {{ ref('int_rule_based_anomaly_detection') }}

),

overall_metrics as (

    select
        'overall' as metric_scope,
        'all_anomalies' as anomaly_type,
        sum(case when is_synthetic_anomaly and predicted_is_anomaly then 1 else 0 end) as true_positive,
        sum(case when not is_synthetic_anomaly and predicted_is_anomaly then 1 else 0 end) as false_positive,
        sum(case when is_synthetic_anomaly and not predicted_is_anomaly then 1 else 0 end) as false_negative,
        sum(case when not is_synthetic_anomaly and not predicted_is_anomaly then 1 else 0 end) as true_negative,
        count(*) as total_records
    from predictions

),

anomaly_types as (

    select synthetic_anomaly_type as anomaly_type
    from predictions
    where is_synthetic_anomaly
    group by 1

),

type_metrics as (

    select
        'by_anomaly_type' as metric_scope,
        anomaly_types.anomaly_type,
        sum(
            case
                when predictions.synthetic_anomaly_type = anomaly_types.anomaly_type
                    and predictions.predicted_anomaly_type = anomaly_types.anomaly_type
                    then 1
                else 0
            end
        ) as true_positive,
        sum(
            case
                when predictions.synthetic_anomaly_type != anomaly_types.anomaly_type
                    and predictions.predicted_anomaly_type = anomaly_types.anomaly_type
                    then 1
                else 0
            end
        ) as false_positive,
        sum(
            case
                when predictions.synthetic_anomaly_type = anomaly_types.anomaly_type
                    and predictions.predicted_anomaly_type != anomaly_types.anomaly_type
                    then 1
                else 0
            end
        ) as false_negative,
        sum(
            case
                when predictions.synthetic_anomaly_type != anomaly_types.anomaly_type
                    and predictions.predicted_anomaly_type != anomaly_types.anomaly_type
                    then 1
                else 0
            end
        ) as true_negative,
        count(*) as total_records
    from anomaly_types
    cross join predictions
    group by 1, 2

),

combined_metrics as (

    select *
    from overall_metrics

    union all

    select *
    from type_metrics

)

select
    metric_scope,
    anomaly_type,
    true_positive,
    false_positive,
    false_negative,
    true_negative,
    total_records,
    true_positive + false_negative as actual_positive_count,
    true_positive + false_positive as predicted_positive_count,
    case
        when true_positive + false_positive = 0 then null
        else true_positive::double / (true_positive + false_positive)
    end as precision,
    case
        when true_positive + false_negative = 0 then null
        else true_positive::double / (true_positive + false_negative)
    end as recall,
    case
        when true_positive = 0 then 0.0
        else 2.0 * true_positive
            / (2.0 * true_positive + false_positive + false_negative)
    end as f1_score
from combined_metrics
