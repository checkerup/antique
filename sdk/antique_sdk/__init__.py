"""antique SDK — typed Python client for the antique anti-detect browser API.

A thin, fully-typed wrapper around the antique REST API.  Uses httpx for
the transport layer and supports transport injection for testability.

Quick start::

    from antique_sdk import AntiqueClient

    with AntiqueClient(base_url="http://127.0.0.1:50325") as client:
        profiles = client.list_profiles()
        uid = client.create_profile(name="my-profile")
        client.start_profile(uid)

"""
from antique_sdk.client import AntiqueClient
from antique_sdk.exceptions import AntiqueAPIError, ProfileNotFound, TransportError
from antique_sdk.models import (
    Profile,
    ProfileCreateRequest,
    HealthStatus,
    InfoStatus,
    ProfileListResponse,
    StartedProfile,
    ActiveProfile,
)

__all__ = [
    "AntiqueClient",
    "AntiqueAPIError",
    "ProfileNotFound",
    "TransportError",
    "Profile",
    "ProfileCreateRequest",
    "HealthStatus",
    "InfoStatus",
    "ProfileListResponse",
    "StartedProfile",
    "ActiveProfile",
]

__version__ = "0.1.0"
