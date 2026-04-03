"""
lead_verifier.py — Email verification with two tiers:
  Tier 1 (free): MX record lookup via dns.resolver
  Tier 2 (paid): ZeroBounce API if ZEROBOUNCE_API_KEY is set
"""

import os
import socket
from typing import Literal

try:
    import dns.resolver
    HAS_DNS = True
except ImportError:
    HAS_DNS = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

VerifyResult = Literal["valid", "invalid", "catch-all", "unknown"]

ZEROBOUNCE_URL = "https://api.zerobounce.net/v2/validate"

# Known disposable email domains
DISPOSABLE_DOMAINS = {
    "mailinator.com", "tempmail.com", "throwaway.email", "guerrillamail.com",
    "sharklasers.com", "grr.la", "yopmail.com", "10minutemail.com",
    "trashmail.com", "fakeinbox.com",
}


def verify_email(email: str) -> tuple[VerifyResult, str]:
    """
    Verify an email address. Returns (status, detail).
    Uses ZeroBounce if API key is available, otherwise falls back to MX check.
    """
    if not email or "@" not in email:
        return "invalid", "malformed email"

    domain = email.split("@")[1].lower()

    # Quick check: disposable domains
    if domain in DISPOSABLE_DOMAINS:
        return "invalid", "disposable email domain"

    # Tier 2: ZeroBounce (if configured)
    zb_key = os.getenv("ZEROBOUNCE_API_KEY", "")
    if zb_key and HAS_REQUESTS:
        return _verify_zerobounce(email, zb_key)

    # Tier 1: MX record check (free)
    return _verify_mx(email, domain)


def _verify_mx(email: str, domain: str) -> tuple[VerifyResult, str]:
    """Check if the domain has valid MX records."""
    if not HAS_DNS:
        # Fallback: try socket connection to port 25
        return _verify_socket(domain)

    try:
        mx_records = dns.resolver.resolve(domain, "MX")
        if mx_records:
            # Check if it's a known catch-all pattern
            mx_hosts = [str(r.exchange).lower() for r in mx_records]
            # Google Workspace and Microsoft 365 are generally reliable
            for host in mx_hosts:
                if "google" in host or "outlook" in host or "microsoft" in host:
                    return "valid", f"MX verified ({host.split('.')[0]})"
            return "valid", f"MX verified ({len(mx_records)} records)"
    except dns.resolver.NXDOMAIN:
        return "invalid", "domain does not exist"
    except dns.resolver.NoAnswer:
        return "invalid", "no MX records"
    except dns.resolver.NoNameservers:
        return "unknown", "DNS timeout"
    except Exception as e:
        return "unknown", f"DNS error: {e}"

    return "unknown", "could not verify"


def _verify_socket(domain: str) -> tuple[VerifyResult, str]:
    """Fallback: check if domain resolves at all."""
    try:
        socket.getaddrinfo(domain, 25)
        return "valid", "domain resolves (socket check)"
    except socket.gaierror:
        return "invalid", "domain does not resolve"
    except Exception:
        return "unknown", "socket check failed"


def _verify_zerobounce(email: str, api_key: str) -> tuple[VerifyResult, str]:
    """Use ZeroBounce API for professional verification."""
    try:
        resp = requests.get(
            ZEROBOUNCE_URL,
            params={"api_key": api_key, "email": email},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status", "").lower()
        sub_status = data.get("sub_status", "")

        if status == "valid":
            return "valid", f"ZeroBounce verified: {sub_status or 'valid'}"
        elif status == "invalid":
            return "invalid", f"ZeroBounce: {sub_status}"
        elif status == "catch-all":
            return "catch-all", "ZeroBounce: catch-all domain"
        elif status == "do_not_mail":
            return "invalid", f"ZeroBounce: do_not_mail ({sub_status})"
        else:
            return "unknown", f"ZeroBounce: {status} / {sub_status}"

    except Exception as e:
        # Fall back to MX check on API failure
        domain = email.split("@")[1]
        return _verify_mx(email, domain)
