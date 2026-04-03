"""
Lead sourcing providers — pluggable adapters for any data source.
"""

from providers.base import LeadProvider
from providers.apollo_provider import ApolloProvider
from providers.hunter_provider import HunterProvider
from providers.csv_provider import CSVProvider
from providers.web_provider import WebProvider

PROVIDER_REGISTRY: dict[str, type[LeadProvider]] = {
    "apollo": ApolloProvider,
    "hunter": HunterProvider,
    "csv": CSVProvider,
    "web": WebProvider,
}

__all__ = [
    "LeadProvider",
    "ApolloProvider",
    "HunterProvider",
    "CSVProvider",
    "WebProvider",
    "PROVIDER_REGISTRY",
]
