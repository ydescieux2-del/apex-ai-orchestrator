"""
Abstract base class for all lead providers.
Every provider normalizes its output to a list of RawLead dicts.
"""

from abc import ABC, abstractmethod
from typing import Any


class LeadProvider(ABC):
    """Base class that every lead data source must implement."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name (e.g., 'Apollo.io')."""
        ...

    @abstractmethod
    def search(self, **kwargs) -> list[dict]:
        """
        Search the provider and return raw lead dicts.
        Each dict should have as many of these fields as available:
          first_name, last_name, email, title, company_name,
          phone, website, industry, company_size, location
        Missing fields will be filled with "" during normalization.
        """
        ...

    def requires_api_key(self) -> bool:
        """Whether this provider needs an API key in .env."""
        return True

    def rate_limit_msg(self) -> str:
        """Human-readable rate limit info."""
        return "No rate limit info available."
