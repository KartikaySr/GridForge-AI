from scripts.telemetry_load import measure


def test_durable_telemetry_load_reconciles_outbox_with_bounded_latency() -> None:
    result = measure(200)
    assert result["rows"] == result["outbox_rows"] == 1000
    assert result["replay_duplicates"] == 5
    # Broad regression ceiling, not a promised production SLO.
    assert float(str(result["ingest_p95_ms"])) < 250
