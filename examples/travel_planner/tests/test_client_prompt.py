"""Tests for the client's breadcrumb prompt helpers (pure string logic, no model)."""

import client


def test_breadcrumb_root():
    assert client._breadcrumb() == "ARD"


def test_breadcrumb_trail():
    assert client._breadcrumb("A2A", "Travel Advisor") == "ARD › A2A › Travel Advisor"


def test_clean_name_strips_redundant_protocol():
    assert client._clean_name("A2A Travel Advisor", "A2A") == "Travel Advisor"
    assert client._clean_name("Forex FX Converter", "MCP") == "Forex FX Converter"


def test_ard_prompt_contains_breadcrumb_and_label():
    p = client.ard_prompt("A2A", "Travel Advisor")
    assert "ARD › A2A › Travel Advisor" in p
    assert "user ❯" in p
    p2 = client.ard_prompt("MCP", "Forex", label="select tool 1-1")
    assert "select tool 1-1 ❯" in p2
