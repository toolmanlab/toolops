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

-- LLM usage table (Claude Code and other LLM session data)
CREATE TABLE IF NOT EXISTS llm_usage (
    timestamp DateTime64(3),
    session_id String,
    project String,
    git_branch String,
    model String,
    input_tokens UInt64,
    output_tokens UInt64,
    cache_creation_tokens UInt64,
    cache_read_tokens UInt64,
    total_tokens UInt64,
    service_tier String,
    source String DEFAULT 'claude_code',
    cc_version String,
    cost_usd Float64 DEFAULT 0,
    INDEX idx_session session_id TYPE bloom_filter GRANULARITY 4,
    INDEX idx_project project TYPE bloom_filter GRANULARITY 4,
    INDEX idx_model model TYPE bloom_filter GRANULARITY 4
) ENGINE = MergeTree()
ORDER BY (timestamp, session_id)
TTL toDateTime(timestamp) + INTERVAL 90 DAY;
