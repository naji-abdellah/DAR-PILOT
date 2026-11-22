"""Scam Listing Detector for DarPilot (M5).

Detects suspicious listings using:
1. Rule-based heuristics (price anomalies, duplicate content, suspicious contacts)
2. scikit-learn ML model trained on synthetic data

Run on 8 GB RAM, no GPU required.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


# ── Configuration ──────────────────────────────────────────────────────────

# Price thresholds (MAD) - listings far below market are suspicious
PRICE_THRESHOLDS = {
    "Apartment": {"min": 300000, "max": 5000000},
    "Villa": {"min": 1000000, "max": 20000000},
    "Studio": {"min": 200000, "max": 2000000},
    "Riad": {"min": 800000, "max": 10000000},
}

# Suspicious contact patterns
SUSPICIOUS_PHONE_PATTERNS = [
    r"^0[5-7]0{7}$",  # Too many zeros
    r"^0[5-7](\d)\1{7}$",  # Repeated digit
]

SUSPICIOUS_EMAIL_PATTERNS = [
    r"^[a-z]{1,3}\d{4,}@",  # Very short name + many digits
    r"@(?:gmail|yahoo|hotmail|outlook)\.com$",  # Free email domains (higher risk)
]

# Suspicious text patterns
SUSPICIOUS_TEXT_PATTERNS = [
    r"urgent|immediate|quick\s+sale|cash\s+only",
    r"no\s+agent|direct\s+owner|bypass",
    r"below\s+market|great\s+deal|investment\s+opportunity",
    r"whatsapp|telegram|signal\s+only",
]


# ── Data Classes ──────────────────────────────────────────────────────────

@dataclass
class ScamSignal:
    """A single scam detection signal."""
    rule_name: str
    severity: str  # critical, high, medium, low
    description: str
    value: Any = None


@dataclass
class ScamResult:
    """Result of scam detection."""
    is_scam: bool
    confidence: float  # 0.0 to 1.0
    signals: List[ScamSignal]
    ml_score: Optional[float] = None


# ── Rule-Based Detection ──────────────────────────────────────────────────

def detect_price_anomaly(listing: Dict[str, Any]) -> List[ScamSignal]:
    """Detect price far below market for property type."""
    signals = []
    prop_type = listing.get("property_type", "")
    price = listing.get("price_mad", 0)
    
    if prop_type in PRICE_THRESHOLDS:
        thresholds = PRICE_THRESHOLDS[prop_type]
        if price < thresholds["min"]:
            signals.append(ScamSignal(
                rule_name="price_too_low",
                severity="high",
                description=f"Price {price:,} MAD far below minimum {thresholds['min']:,} MAD for {prop_type}",
                value={"price": price, "min_expected": thresholds["min"]},
            ))
        elif price > thresholds["max"]:
            signals.append(ScamSignal(
                rule_name="price_too_high",
                severity="medium",
                description=f"Price {price:,} MAD unusually high for {prop_type}",
                value={"price": price, "max_expected": thresholds["max"]},
            ))
    return signals


def detect_duplicate_content(listing: Dict[str, Any], all_listings: List[Dict[str, Any]]) -> List[ScamSignal]:
    """Detect copied/duplicate listing descriptions."""
    signals = []
    desc = listing.get("description", "").strip().lower()
    if not desc or len(desc) < 20:
        return signals
    
    # Hash-based exact duplicate detection
    desc_hash = hashlib.md5(desc.encode()).hexdigest()[:16]
    for other in all_listings:
        if other.get("id") == listing.get("id"):
            continue
        other_desc = other.get("description", "").strip().lower()
        if other_desc and hashlib.md5(other_desc.encode()).hexdigest()[:16] == desc_hash:
            signals.append(ScamSignal(
                rule_name="duplicate_description",
                severity="high",
                description=f"Exact duplicate description found (listing #{other.get('id')})",
                value={"duplicate_of": other.get("id")},
            ))
            break
    
    # Near-duplicate: check for very similar descriptions
    for other in all_listings:
        if other.get("id") == listing.get("id"):
            continue
        other_desc = other.get("description", "").strip().lower()
        if other_desc and len(other_desc) > 20:
            # Simple Jaccard similarity on words
            words1 = set(desc.split())
            words2 = set(other_desc.split())
            if words1 and words2:
                intersection = len(words1 & words2)
                union = len(words1 | words2)
                similarity = intersection / union if union > 0 else 0
                if similarity > 0.85:
                    signals.append(ScamSignal(
                        rule_name="near_duplicate_description",
                        severity="medium",
                        description=f"Near-duplicate description ({similarity:.0%} similar to listing #{other.get('id')})",
                        value={"similar_to": other.get("id"), "similarity": similarity},
                    ))
                    break
    return signals


def detect_suspicious_contact(listing: Dict[str, Any]) -> List[ScamSignal]:
    """Detect suspicious phone/email patterns."""
    signals = []
    
    phone = listing.get("phone", "") or listing.get("contact_phone", "")
    email = listing.get("email", "") or listing.get("contact_email", "")
    
    for pattern in SUSPICIOUS_PHONE_PATTERNS:
        if re.search(pattern, phone):
            signals.append(ScamSignal(
                rule_name="suspicious_phone",
                severity="medium",
                description=f"Suspicious phone pattern: {phone}",
                value={"phone": phone},
            ))
    
    for pattern in SUSPICIOUS_EMAIL_PATTERNS:
        if re.search(pattern, email, re.IGNORECASE):
            signals.append(ScamSignal(
                rule_name="suspicious_email",
                severity="low",
                description=f"Suspicious email pattern: {email}",
                value={"email": email},
            ))
    
    return signals


def detect_suspicious_text(listing: Dict[str, Any]) -> List[ScamSignal]:
    """Detect suspicious keywords/phrases in title/description."""
    signals = []
    
    text = " ".join([
        listing.get("title", ""),
        listing.get("description", ""),
    ]).lower()
    
    for pattern in SUSPICIOUS_TEXT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            signals.append(ScamSignal(
                rule_name="suspicious_text",
                severity="low",
                description=f"Suspicious phrase detected: {pattern}",
                value={"pattern": pattern},
            ))
    return signals


def detect_missing_info(listing: Dict[str, Any]) -> List[ScamSignal]:
    """Detect listings with missing critical information."""
    signals = []
    
    required_fields = ["title", "description", "price_mad", "city", "property_type"]
    for field in required_fields:
        if not listing.get(field):
            signals.append(ScamSignal(
                rule_name="missing_info",
                severity="medium",
                description=f"Missing required field: {field}",
                value={"field": field},
            ))
    
    # Very short description
    desc = listing.get("description", "")
    if desc and len(desc.strip()) < 50:
        signals.append(ScamSignal(
            rule_name="short_description",
            severity="low",
            description=f"Description too short ({len(desc)} chars)",
            value={"length": len(desc)},
        ))
    
    return signals


# ── ML-Based Detection ────────────────────────────────────────────────────

class ScamDetectorML:
    """Isolation Forest based anomaly detector for listings."""
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(max_features=500, stop_words=None)
        self.scaler = StandardScaler()
        self.model = IsolationForest(contamination=0.1, random_state=42, n_estimators=100)
        self.is_trained = False
        self.feature_names = []
    
    def _extract_features(self, listing: Dict[str, Any]) -> Dict[str, float]:
        """Extract numerical features from listing."""
        desc = listing.get("description", "")
        title = listing.get("title", "")
        price = listing.get("price_mad", 0)
        
        features = {
            "price": price,
            "title_length": len(title),
            "desc_length": len(desc),
            "desc_word_count": len(desc.split()),
            "has_phone": 1 if listing.get("phone") else 0,
            "has_email": 1 if listing.get("email") else 0,
            "price_per_word": price / max(len(desc.split()), 1),
        }
        
        # Property type one-hot
        prop_type = listing.get("property_type", "")
        for pt in ["Apartment", "Villa", "Studio", "Riad"]:
            features[f"is_{pt.lower()}"] = 1 if prop_type == pt else 0
        
        # City
        city = listing.get("city", "")
        features["is_casablanca"] = 1 if "casablanca" in city.lower() else 0
        features["is_marrakech"] = 1 if "marrakech" in city.lower() else 0
        
        return features
    
    def _text_features(self, listings: List[Dict[str, Any]]) -> np.ndarray:
        """Extract TF-IDF features from descriptions."""
        texts = [l.get("description", "") + " " + l.get("title", "") for l in listings]
        return self.vectorizer.transform(texts).toarray()
    
    def train(self, listings: List[Dict[str, Any]]) -> None:
        """Train the anomaly detector on listings."""
        if not SKLEARN_AVAILABLE:
            return
        
        # Numerical features
        num_features_list = [self._extract_features(l) for l in listings]
        self.feature_names = list(num_features_list[0].keys()) if num_features_list else []
        
        num_features = np.array([[f[name] for name in self.feature_names] for f in num_features_list])
        num_features_scaled = self.scaler.fit_transform(num_features)
        
        # Text features - fit and transform
        texts = [l.get("description", "") + " " + l.get("title", "") for l in listings]
        text_features = self.vectorizer.fit_transform(texts).toarray()
        
        # Combine
        combined = np.hstack([num_features_scaled, text_features])
        
        # Train Isolation Forest
        self.model.fit(combined)
        self.is_trained = True
    
    def predict(self, listing: Dict[str, Any]) -> Tuple[float, bool]:
        """Predict anomaly score. Returns (score, is_anomaly)."""
        if not self.is_trained or not SKLEARN_AVAILABLE:
            return 0.5, False
        
        # Numerical features
        features = self._extract_features(listing)
        num_array = np.array([[features.get(name, 0) for name in self.feature_names]])
        num_scaled = self.scaler.transform(num_array)
        
        # Text features
        text = listing.get("description", "") + " " + listing.get("title", "")
        text_array = self.vectorizer.transform([text]).toarray()
        
        # Combine
        combined = np.hstack([num_scaled, text_array])
        
        # Predict
        score = self.model.decision_function(combined)[0]
        is_anomaly = self.model.predict(combined)[0] == -1
        
        # Normalize score to 0-1 (higher = more anomalous)
        normalized_score = 1 / (1 + np.exp(score))  # Sigmoid
        
        return float(normalized_score), bool(is_anomaly)
    
    def save(self, path: str) -> None:
        """Save model to disk."""
        with open(path, "wb") as f:
            pickle.dump({
                "vectorizer": self.vectorizer,
                "scaler": self.scaler,
                "model": self.model,
                "feature_names": self.feature_names,
                "is_trained": self.is_trained,
            }, f)
    
    @classmethod
    def load(cls, path: str) -> "ScamDetectorML":
        """Load model from disk."""
        detector = cls()
        with open(path, "rb") as f:
            data = pickle.load(f)
        detector.vectorizer = data["vectorizer"]
        detector.scaler = data["scaler"]
        detector.model = data["model"]
        detector.feature_names = data["feature_names"]
        detector.is_trained = data["is_trained"]
        return detector


# ── Main Detection Function ──────────────────────────────────────────────

# Global ML detector instance
_ml_detector: Optional[ScamDetectorML] = None


def initialize_detector(listings: List[Dict[str, Any]]) -> None:
    """Initialize and train the ML detector on existing listings."""
    global _ml_detector
    if SKLEARN_AVAILABLE:
        _ml_detector = ScamDetectorML()
        _ml_detector.train(listings)


def detect_scam(
    listing: Dict[str, Any],
    all_listings: Optional[List[Dict[str, Any]]] = None,
) -> ScamResult:
    """Run full scam detection on a listing."""
    all_signals = []
    
    # Rule-based checks
    all_signals.extend(detect_price_anomaly(listing))
    all_signals.extend(detect_suspicious_contact(listing))
    all_signals.extend(detect_suspicious_text(listing))
    all_signals.extend(detect_missing_info(listing))
    
    if all_listings:
        all_signals.extend(detect_duplicate_content(listing, all_listings))
    
    # ML-based check
    ml_score = None
    if _ml_detector and _ml_detector.is_trained:
        ml_score, is_anomaly = _ml_detector.predict(listing)
        if is_anomaly:
            all_signals.append(ScamSignal(
                rule_name="ml_anomaly",
                severity="high",
                description=f"ML model flagged as anomalous (score: {ml_score:.2f})",
                value={"score": ml_score},
            ))
    
    # Calculate overall confidence
    severity_weights = {"critical": 1.0, "high": 0.8, "medium": 0.5, "low": 0.2}
    max_confidence = max([severity_weights.get(s.severity, 0) for s in all_signals], default=0)
    
    # Boost confidence if ML agrees
    if ml_score and ml_score > 0.7:
        max_confidence = min(1.0, max_confidence + 0.2)
    
    is_scam = max_confidence > 0.6 or any(s.severity in ("critical", "high") for s in all_signals)
    
    return ScamResult(
        is_scam=is_scam,
        confidence=max_confidence,
        signals=all_signals,
        ml_score=ml_score,
    )


# ── Batch Detection ──────────────────────────────────────────────────────

def scan_all_listings(listings: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], ScamResult]]:
    """Scan all listings for scams."""
    # Initialize ML detector if not done
    if _ml_detector is None and SKLEARN_AVAILABLE:
        initialize_detector(listings)
    
    results = []
    for listing in listings:
        result = detect_scam(listing, listings)
        results.append((listing, result))
    
    return results


def get_scam_summary(results: List[Tuple[Dict[str, Any], ScamResult]]) -> Dict[str, Any]:
    """Generate summary of scam detection results."""
    total = len(results)
    scams = sum(1 for _, r in results if r.is_scam)
    
    by_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for _, r in results:
        for s in r.signals:
            by_severity[s.severity] += 1
    
    return {
        "total_listings": total,
        "flagged_as_scam": scams,
        "clean": total - scams,
        "signals_by_severity": by_severity,
    }


# ── Demo/Training Data Generation ────────────────────────────────────────

def generate_synthetic_training_data(n_clean: int = 100, n_scam: int = 20) -> List[Dict[str, Any]]:
    """Generate synthetic listings for training."""
    import random
    
    cities = ["Casablanca", "Marrakech", "Rabat", "Tangier", "Fes", "Agadir"]
    neighborhoods = {
        "Casablanca": ["Maarif", "Anfa", "Bourgogne", "Gauthier"],
        "Marrakech": ["Gueliz", "Palmeraie", "Medina", "Hivernage"],
        "Rabat": ["Agdal", "Hassan", "Souissi", "Ocean"],
    }
    prop_types = ["Apartment", "Villa", "Studio", "Riad"]
    
    listings = []
    
    # Clean listings
    for i in range(n_clean):
        city = random.choice(cities)
        prop_type = random.choice(prop_types)
        thresholds = PRICE_THRESHOLDS[prop_type]
        price = random.randint(thresholds["min"], thresholds["max"])
        
        listings.append({
            "id": i + 1,
            "title": f"{prop_type} in {random.choice(neighborhoods.get(city, ['Center']))}",
            "description": f"Beautiful {prop_type.lower()} in {city}. Spacious and modern with great amenities.",
            "price_mad": price,
            "city": city,
            "neighborhood": random.choice(neighborhoods.get(city, ["Center"])),
            "property_type": prop_type,
            "status": "available",
            "agent_id": 1,
            "phone": f"06{random.randint(10000000, 99999999)}",
            "email": f"agent{i}@realestate.ma",
        })
    
    # Scam listings
    scam_templates = [
        # Too cheap
        {"title": "Amazing Villa Cheap", "price_factor": 0.1, "desc": "Urgent sale! Villa at incredible price. Cash only. Contact WhatsApp only."},
        # Duplicate content
        {"title": "Studio in Center", "price_factor": 1.0, "desc": "Beautiful studio in center. Spacious and modern with great amenities."},
        # Suspicious text
        {"title": "Quick Sale Apartment", "price_factor": 0.5, "desc": "Immediate sale! Below market price. Great investment opportunity. No agents, direct owner."},
        # Missing info
        {"title": "Property", "price_factor": 1.0, "desc": "Nice property."},
    ]
    
    for i in range(n_scam):
        template = random.choice(scam_templates)
        city = random.choice(cities)
        prop_type = random.choice(prop_types)
        thresholds = PRICE_THRESHOLDS[prop_type]
        base_price = random.randint(thresholds["min"], thresholds["max"])
        price = int(base_price * template["price_factor"])
        
        listings.append({
            "id": n_clean + i + 1,
            "title": template["title"],
            "description": template["desc"],
            "price_mad": price,
            "city": city,
            "neighborhood": random.choice(neighborhoods.get(city, ["Center"])),
            "property_type": prop_type,
            "status": "available",
            "agent_id": 1,
            "phone": "0600000000" if random.random() > 0.5 else f"06{random.randint(10000000, 99999999)}",
            "email": f"scammer{i}@gmail.com",
        })
    
    return listings


# ── CLI / Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("Generating synthetic training data...")
    listings = generate_synthetic_training_data(200, 30)
    
    print("Training ML detector...")
    initialize_detector(listings)
    
    print("Scanning all listings...")
    results = scan_all_listings(listings)
    
    summary = get_scam_summary(results)
    print(f"\n=== SCAM DETECTION SUMMARY ===")
    print(f"Total listings: {summary['total_listings']}")
    print(f"Flagged as scam: {summary['flagged_as_scam']}")
    print(f"Clean: {summary['clean']}")
    print(f"Signals by severity: {summary['signals_by_severity']}")
    
    print("\n=== FLAGGED LISTINGS ===")
    for listing, result in results:
        if result.is_scam:
            print(f"\n#{listing['id']}: {listing['title']} ({listing['price_mad']:,} MAD)")
            print(f"  Confidence: {result.confidence:.2f}")
            for s in result.signals:
                print(f"  - [{s.severity.upper()}] {s.rule_name}: {s.description}")
            if result.ml_score:
                print(f"  ML Score: {result.ml_score:.2f}")