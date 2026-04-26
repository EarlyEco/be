from typing import Any

from pydantic import BaseModel, Field


class CommunityMapPointsResponse(BaseModel):
    """Same pin shape as overview `hotspots`; UI may read `points`, `hotspots`, or `locations`."""

    points: list[dict[str, Any]] = Field(default_factory=list)
    hotspots: list[dict[str, Any]] = Field(default_factory=list)
    locations: list[dict[str, Any]] = Field(default_factory=list)
