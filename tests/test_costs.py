from tizita import costs

PRICES = {"free": {"usd": 0}, "p.img": {"usd": None}, "p.text": {"usd": 1.0}}


def _line(provider, basis, status="ok", latency=1000, price=0.0, tier="free_hosted"):
    return {
        "ts": "2026-11-26T00:00:00.000Z",
        "stage": "keyframes",
        "provider": provider,
        "tier": tier,
        "status": status,
        "latency_ms": latency,
        "gpu_seconds": None,
        "cost_basis": f"pricing.yaml#{basis}" if basis else None,
        "cost_list_price_usd": price,
        "cost_actual_usd": 0.0,
    }


def test_null_price_is_unknown_even_if_the_log_says_zero():
    assert costs.list_price(_line("img", "p.img"), PRICES) is None
    assert costs.list_price(_line("txt", "p.text", price=0.5), PRICES) == 0.5
    assert costs.list_price(_line("pad", None, tier="deterministic"), PRICES) == 0.0
    assert costs.list_price(_line("space", None), PRICES) is None


def test_percentiles_nearest_rank():
    assert costs.percentile([1, 2, 3, 4], 50) == 2
    assert costs.percentile([1, 2, 3, 4], 95) == 4
    assert costs.percentile([], 50) is None


def test_render_and_inject_replace_only_the_generated_section():
    lines = [_line("img", "p.img"), _line("img", "p.img", status="error")]
    events = [{"type": "run_summary", "cache_hits": 3, "ran": ["a"]}]
    body = costs.render(lines, events, PRICES, {"img": "pool:x"})
    assert "| pool:x | 2 | 1 | 1 | img |" in body
    assert "75% hit rate" in body and "unknown" in body
    doc = f"head\n{costs.BEGIN}\nold\n{costs.END}\ntail\n"
    out = costs.inject(doc, body)
    assert out.startswith("head\n") and out.endswith("tail\n") and "old" not in out
    assert costs.inject(out, body) == out
