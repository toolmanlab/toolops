from toolops.collector.loki import generate_loki_config
from toolops.collector.otel import generate_otel_config
from toolops.collector.prometheus import generate_scrape_config

__all__ = ["generate_loki_config", "generate_otel_config", "generate_scrape_config"]
