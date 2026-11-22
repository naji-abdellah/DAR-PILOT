"""Tests for M5 Scam Listing Detector."""

import os
import tempfile

os.environ["DARPILOT_DB_PATH"] = tempfile.mkstemp(suffix=".db")[1]
os.environ["DARPILOT_SECRET_KEY"] = "test-secret-do-not-use-in-production"
os.environ["DARPILOT_LOGIN_RATE_LIMIT"] = "100/minute"
os.environ["DARPILOT_RAG_THRESHOLD"] = "0.60"

import pytest  # noqa: E402

from ai.scam_detector import (  # noqa: E402
    detect_price_anomaly,
    detect_duplicate_content,
    detect_suspicious_contact,
    detect_suspicious_text,
    detect_missing_info,
    detect_scam,
    scan_all_listings,
    get_scam_summary,
    generate_synthetic_training_data,
    ScamSignal,
    ScamResult,
)


def test_price_anomaly_too_low():
    """Price far below market should be flagged."""
    listing = {"property_type": "Apartment", "price_mad": 50000}
    signals = detect_price_anomaly(listing)
    assert any(s.rule_name == "price_too_low" for s in signals)


def test_price_anomaly_too_high():
    """Price far above market should be flagged."""
    listing = {"property_type": "Studio", "price_mad": 5000000}
    signals = detect_price_anomaly(listing)
    assert any(s.rule_name == "price_too_high" for s in signals)


def test_price_normal():
    """Normal price should not be flagged."""
    listing = {"property_type": "Apartment", "price_mad": 1500000}
    signals = detect_price_anomaly(listing)
    assert len(signals) == 0


def test_duplicate_content_exact():
    """Exact duplicate descriptions should be detected."""
    listing = {"id": 1, "description": "Beautiful villa with pool in Marrakech"}
    all_listings = [
        {"id": 2, "description": "Beautiful villa with pool in Marrakech"},
    ]
    signals = detect_duplicate_content(listing, all_listings)
    assert any(s.rule_name == "duplicate_description" for s in signals)


def test_duplicate_content_none():
    """Unique description should not be flagged."""
    listing = {"id": 1, "description": "Unique description here"}
    all_listings = [
        {"id": 2, "description": "Completely different description"},
    ]
    signals = detect_duplicate_content(listing, all_listings)
    assert not any(s.rule_name == "duplicate_description" for s in signals)


def test_suspicious_phone():
    """Suspicious phone patterns should be detected."""
    listing = {"phone": "0600000000"}
    signals = detect_suspicious_contact(listing)
    assert any(s.rule_name == "suspicious_phone" for s in signals)


def test_suspicious_email():
    """Suspicious email patterns should be detected."""
    listing = {"email": "ab12345@gmail.com"}
    signals = detect_suspicious_contact(listing)
    assert any(s.rule_name == "suspicious_email" for s in signals)


def test_suspicious_text():
    """Suspicious text patterns should be detected."""
    listing = {"description": "Urgent sale! Cash only. Quick sale below market."}
    signals = detect_suspicious_text(listing)
    assert any(s.rule_name == "suspicious_text" for s in signals)


def test_missing_info():
    """Missing required fields should be flagged."""
    listing = {"title": "Test"}  # missing description, price, etc.
    signals = detect_missing_info(listing)
    assert any(s.rule_name == "missing_info" for s in signals)


def test_short_description():
    """Very short description should be flagged."""
    listing = {"description": "Nice"}
    signals = detect_missing_info(listing)
    assert any(s.rule_name == "short_description" for s in signals)


def test_detect_scam_clean_listing():
    """Clean listing should not be flagged as scam."""
    listing = {
        "id": 1,
        "title": "Modern Apartment in Maarif",
        "description": "Beautiful 2-bedroom apartment with modern amenities in a great location.",
        "price_mad": 1500000,
        "city": "Casablanca",
        "property_type": "Apartment",
        "phone": "0612345678",
        "email": "agent@realestate.ma",
    }
    all_listings = [listing]
    result = detect_scam(listing, all_listings)
    # Clean listing should have low confidence and not be flagged
    assert not result.is_scam or result.confidence < 0.6


def test_detect_scam_price_too_low():
    """Listing with too low price should be flagged."""
    listing = {
        "id": 1,
        "title": "Cheap Villa",
        "description": "Great villa at amazing price!",
        "price_mad": 50000,  # Way too low
        "city": "Marrakech",
        "property_type": "Villa",
        "phone": "0612345678",
        "email": "agent@realestate.ma",
    }
    all_listings = [listing]
    result = detect_scam(listing, all_listings)
    assert result.is_scam
    assert any(s.rule_name == "price_too_low" for s in result.signals)


def test_detect_scam_duplicate():
    """Duplicate listing should be flagged."""
    listing = {
        "id": 2,
        "title": "Villa in Palmeraie",
        "description": "Luxury villa with pool in Palmeraie, Marrakech.",
        "price_mad": 4500000,
        "city": "Marrakech",
        "property_type": "Villa",
    }
    all_listings = [
        {"id": 1, "title": "Villa in Palmeraie", "description": "Luxury villa with pool in Palmeraie, Marrakech.", "price_mad": 4500000, "city": "Marrakech", "property_type": "Villa"},
        listing,
    ]
    result = detect_scam(listing, all_listings)
    assert result.is_scam
    assert any(s.rule_name == "duplicate_description" for s in result.signals)


def test_scan_all_listings():
    """Batch scanning should work."""
    listings = generate_synthetic_training_data(50, 10)
    results = scan_all_listings(listings)
    assert len(results) == 60
    
    summary = get_scam_summary(results)
    assert summary["total_listings"] == 60
    assert summary["flagged_as_scam"] >= 10  # At least the scam ones


def test_scam_result_structure():
    """ScamResult should have correct structure."""
    listing = {
        "id": 1,
        "title": "Test",
        "description": "Test description",
        "price_mad": 1000000,
        "city": "Casablanca",
        "property_type": "Apartment",
    }
    result = detect_scam(listing, [listing])
    assert isinstance(result, ScamResult)
    assert isinstance(result.is_scam, bool)
    assert isinstance(result.confidence, float)
    assert isinstance(result.signals, list)
    for s in result.signals:
        assert isinstance(s, ScamSignal)
        assert s.rule_name
        assert s.severity in ("critical", "high", "medium", "low")
        assert s.description


def test_synthetic_data_generation():
    """Synthetic data generation should produce valid listings."""
    listings = generate_synthetic_training_data(100, 20)
    assert len(listings) == 120
    
    # Check structure
    for l in listings:
        assert "id" in l
        assert "title" in l
        assert "description" in l
        assert "price_mad" in l
        assert "city" in l
        assert "property_type" in l
        assert l["property_type"] in ("Apartment", "Villa", "Studio", "Riad")
        assert l["price_mad"] > 0