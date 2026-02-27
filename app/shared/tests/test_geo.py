# pyright: reportUnknownParameterType=false, reportMissingParameterType=false
"""Unit tests for geographic utility functions."""

from app.shared.geo import haversine_distance


def test_same_point_returns_zero():
    """Distance from a point to itself should be zero."""
    dist = haversine_distance(56.9496, 24.1052, 56.9496, 24.1052)
    assert dist == 0.0


def test_known_distance_riga_to_jurmala():
    """Riga center to Jurmala (~22 km) within 5% tolerance."""
    # Riga: 56.9496, 24.1052
    # Jurmala: 56.968, 23.770
    dist = haversine_distance(56.9496, 24.1052, 56.968, 23.770)
    assert 20_000 < dist < 24_000, f"Expected ~22km, got {dist:.0f}m"


def test_short_distance_within_riga():
    """Two nearby stops in Riga (~150m apart)."""
    dist = haversine_distance(56.9496, 24.1052, 56.9497, 24.1073)
    assert 100 < dist < 250, f"Expected ~150m, got {dist:.0f}m"


def test_symmetry():
    """haversine(A, B) == haversine(B, A)."""
    d1 = haversine_distance(56.9496, 24.1052, 56.968, 23.770)
    d2 = haversine_distance(56.968, 23.770, 56.9496, 24.1052)
    assert abs(d1 - d2) < 0.01, f"Not symmetric: {d1} vs {d2}"
