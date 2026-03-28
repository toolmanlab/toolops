-- Metrics table (time series)
CREATE TABLE IF NOT EXISTS metrics (
    timestamp DateTime64(3),
    service String,
    metric_name String,
    metric_value Float64,
    labels Map(String, String)
) ENGINE = MergeTree()
ORDER BY (service, metric_name, timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY;

-- Traces table (distributed tracing)
CREATE TABLE IF NOT EXISTS traces (
    trace_id String,
    span_id String,
    parent_span_id String,
    service String,
    operation String,
    start_time DateTime64(3),
    duration_ms Float64,
    status_code UInt8,
    attributes Map(String, String)
) ENGINE = MergeTree()
ORDER BY (service, start_time, trace_id)
TTL toDateTime(start_time) + INTERVAL 30 DAY;

-- Logs table (structured logs)
CREATE TABLE IF NOT EXISTS logs (
    timestamp DateTime64(3),
    service String,
    level String,
    message String,
    trace_id String,
    attributes Map(String, String)
) ENGINE = MergeTree()
ORDER BY (service, timestamp)
TTL toDateTime(timestamp) + INTERVAL 30 DAY;
