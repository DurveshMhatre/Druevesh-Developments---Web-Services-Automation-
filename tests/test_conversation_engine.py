"""Unit tests for the conversation engine."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from phase2_whatsapp.conversation_engine import (
    _fallback_response,
    _format_collected_data,
    _format_history,
    _format_packages,
    recommend_package,
)
from phase2_whatsapp.stage_manager import Stage


class TestFormatters:
    """Test internal formatting helpers."""

    def test_format_packages_not_empty(self):
        result = _format_packages()
        assert "Starter" in result
        assert "Business" in result
        assert "Premium" in result

    def test_format_empty_history(self):
        result = _format_history([])
        assert "No previous" in result

    def test_format_history_with_messages(self):
        history = [
            {"Direction": "out", "Message": "Hello"},
            {"Direction": "in", "Message": "Hi there"},
        ]
        result = _format_history(history)
        assert "[YOU]" in result
        assert "[CLIENT]" in result

    def test_format_empty_collected_data(self):
        result = _format_collected_data({})
        assert "Nothing collected" in result

    def test_format_collected_data_with_values(self):
        data = {"business_name": "Chai Wala", "services_description": "Tea shop"}
        result = _format_collected_data(data)
        assert "Chai Wala" in result
        assert "Tea shop" in result


class TestFallbackResponse:
    """Test fallback responses for each stage."""

    def test_welcome_fallback(self):
        resp = _fallback_response(Stage.WELCOME)
        assert "response" in resp
        assert resp["should_advance_stage"] is False
        assert len(resp["response"]) > 0

    def test_requirements_fallback(self):
        resp = _fallback_response(Stage.REQUIREMENTS)
        assert "response" in resp

    def test_package_fallback(self):
        resp = _fallback_response(Stage.PACKAGE)
        assert "response" in resp


class TestRecommendPackage:
    """Test the rule-based package recommendation."""

    def test_ecommerce_gets_premium(self):
        data = {"features": "e-commerce, online store"}
        pkg = recommend_package(data)
        assert pkg["name"] == "Premium"

    def test_booking_gets_premium(self):
        data = {"features": "online booking system, admin panel"}
        pkg = recommend_package(data)
        assert pkg["name"] == "Premium"

    def test_many_pages_gets_premium(self):
        data = {"pages_needed": "15 pages"}
        pkg = recommend_package(data)
        assert pkg["name"] == "Premium"

    def test_medium_pages_gets_business(self):
        data = {"pages_needed": "5 pages"}
        pkg = recommend_package(data)
        assert pkg["name"] == "Business"

    def test_low_budget_gets_starter(self):
        data = {"budget": "kam budget hai", "pages_needed": "2"}
        pkg = recommend_package(data)
        assert pkg["name"] == "Starter"

    def test_default_is_business(self):
        data = {"pages_needed": "3", "features": "contact form"}
        pkg = recommend_package(data)
        assert pkg["name"] == "Business"
