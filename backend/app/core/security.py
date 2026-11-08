"""Compatibility imports for token verification.

Password hashing and local JWT minting are not the account system. Zitadel
issues access tokens; ``app.core.oidc`` checks them.
"""
from app.core.oidc import InvalidAccessToken, verify_access_token

__all__ = ["InvalidAccessToken", "verify_access_token"]
