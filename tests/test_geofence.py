"""Unit tests for geofence point-in-polygon."""

from app.geofence import get_geofence, is_inside_geofence, point_in_polygon


def test_point_inside_square():
    square = [[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0]]
    assert point_in_polygon(1.0, 1.0, square) is True


def test_point_outside_square():
    square = [[0.0, 0.0], [0.0, 2.0], [2.0, 2.0], [2.0, 0.0]]
    assert point_in_polygon(3.0, 1.0, square) is False


def test_seed_positions_vs_default_zone():
    # Alpha / Bravo inside; Charlie outside (seed coords)
    assert is_inside_geofence(-34.6037, -58.3816) is True
    assert is_inside_geofence(-34.6050, -58.3800) is True
    assert is_inside_geofence(-34.6100, -58.3900) is False


def test_get_geofence_shape():
    g = get_geofence()
    assert g["name"]
    assert len(g["polygon"]) >= 3
