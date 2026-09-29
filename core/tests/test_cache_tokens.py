"""Tests for cache token tracking in optimizer cost parsing."""

import json
import pytest
from cap_evolve.harness import _parse_optimizer_cost


def test_parse_optimizer_cost_with_cache_tokens():
    """Test that cache tokens are correctly extracted from optimizer output."""
    # Simulate output from claude-code with cache tokens
    output = json.dumps({
        "cost": {
            "total_cost_usd": 15.84,
            "tokens": 281482,
            "cache_read_tokens": 13182183,
            "cache_creation_tokens": 361415
        }
    })
    
    result = _parse_optimizer_cost(output)
    
    assert result is not None
    assert result["cost_usd"] == 15.84
    assert result["tokens"] == 281482
    assert result["cache_read_tokens"] == 13182183
    assert result["cache_creation_tokens"] == 361415


def test_parse_optimizer_cost_without_cache_tokens():
    """Test that missing cache tokens don't break parsing."""
    output = json.dumps({
        "cost": {
            "total_cost_usd": 5.0,
            "tokens": 10000
        }
    })
    
    result = _parse_optimizer_cost(output)
    
    assert result is not None
    assert result["cost_usd"] == 5.0
    assert result["tokens"] == 10000
    assert "cache_read_tokens" not in result
    assert "cache_creation_tokens" not in result


def test_parse_optimizer_cost_partial_cache_tokens():
    """Test parsing when only one cache token field is present."""
    output = json.dumps({
        "cost": {
            "total_cost_usd": 3.5,
            "tokens": 5000,
            "cache_read_tokens": 100000
        }
    })
    
    result = _parse_optimizer_cost(output)
    
    assert result is not None
    assert result["cost_usd"] == 3.5
    assert result["tokens"] == 5000
    assert result["cache_read_tokens"] == 100000
    assert "cache_creation_tokens" not in result


def test_parse_optimizer_cost_no_cost_block():
    """Test that None is returned when no cost block exists."""
    output = json.dumps({"other": "data"})
    
    result = _parse_optimizer_cost(output)
    
    assert result is None


def test_parse_optimizer_cost_empty_string():
    """Test that None is returned for empty input."""
    result = _parse_optimizer_cost("")
    assert result is None
    
    result = _parse_optimizer_cost("   ")
    assert result is None


def test_parse_optimizer_cost_jsonl_stream():
    """Test parsing from JSONL stream with cache tokens."""
    lines = [
        json.dumps({"type": "init"}),
        json.dumps({
            "cost": {
                "total_cost_usd": 2.5,
                "tokens": 8000,
                "cache_read_tokens": 50000,
                "cache_creation_tokens": 10000
            }
        }),
        json.dumps({"type": "final"})
    ]
    output = "\n".join(lines)
    
    result = _parse_optimizer_cost(output)
    
    assert result is not None
    assert result["cost_usd"] == 2.5
    assert result["tokens"] == 8000
    assert result["cache_read_tokens"] == 50000
    assert result["cache_creation_tokens"] == 10000


def test_parse_optimizer_cost_camel_case_fields():
    """Test parsing with camelCase field names (alternative naming convention)."""
    output = json.dumps({
        "cost": {
            "total_cost_usd": 4.2,
            "tokens": 12000,
            "cacheReadInputTokens": 75000,
            "cacheCreationInputTokens": 15000
        }
    })
    
    result = _parse_optimizer_cost(output)
    
    assert result is not None
    assert result["cost_usd"] == 4.2
    assert result["tokens"] == 12000
    assert result["cache_read_tokens"] == 75000
    assert result["cache_creation_tokens"] == 15000
