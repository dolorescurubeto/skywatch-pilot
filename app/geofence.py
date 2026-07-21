"""Authorized flight zone (geofence) for SkyWatch Pilot."""

from __future__ import annotations

# Polygon as [lat, lon] rings (closed implicitly). Covers Alpha + Bravo; Charlie is outside.
DEFAULT_GEOFENCE = {
    "id": "zone_ba_centro",
    "name": "Authorized flight zone",
    "polygon": [
        [-34.6000, -58.3850],
        [-34.6000, -58.3750],
        [-34.6080, -58.3750],
        [-34.6080, -58.3850],
    ],
}


def get_geofence() -> dict:
    """Return the active geofence definition (copy-safe for API)."""
    return {
        "id": DEFAULT_GEOFENCE["id"],
        "name": DEFAULT_GEOFENCE["name"],
        "polygon": [list(p) for p in DEFAULT_GEOFENCE["polygon"]],
    }


def point_in_polygon(lat: float, lon: float, polygon: list[list[float]]) -> bool:
    """
    Ray-casting point-in-polygon.
    polygon vertices are [lat, lon]; treats lon as x and lat as y.
    """
    if len(polygon) < 3:
        return False

    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        yi, xi = polygon[i][0], polygon[i][1]
        yj, xj = polygon[j][0], polygon[j][1]
        intersects = ((yi > lat) != (yj > lat)) and (
            lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-15) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def is_inside_geofence(lat: float | None, lon: float | None) -> bool | None:
    """
    True if inside, False if outside, None if coordinates missing.
    """
    if lat is None or lon is None:
        return None
    return point_in_polygon(float(lat), float(lon), DEFAULT_GEOFENCE["polygon"])
