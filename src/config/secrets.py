"""Secrets management for MikoV2.

Reads secrets from Docker secrets or environment variables.
All secrets masked in logs. No global state (Y-353).
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Secrets:
    """Docker secrets container.
    
    All secrets read from /run/secrets/ (Docker) or environment.
    Values are masked when logged.
    
    Fields:
        api_key: Exchange API key.
        api_secret: Exchange API secret.
        dashboard_password: Dashboard auth password.
    """
    
    api_key: str
    api_secret: str
    dashboard_password: str
    
    def mask_api_key(self) -> str:
        """Return masked API key for logging.
        
        Returns:
            Masked key (first 4 + *** + last 4).
        """
        if len(self.api_key) <= 8:
            return "***"
        return f"{self.api_key[:4]}***{self.api_key[-4:]}"
    
    def mask_api_secret(self) -> str:
        """Return masked API secret for logging.
        
        Returns:
            Masked secret (always ***).
        """
        return "***"
    
    def validate(self) -> None:
        """Validate all secrets are non-empty.
        
        Raises:
            ValueError: If any secret is empty.
        """
        if not self.api_key:
            raise ValueError("api_key cannot be empty")
        if not self.api_secret:
            raise ValueError("api_secret cannot be empty")
        if not self.dashboard_password:
            raise ValueError("dashboard_password cannot be empty")


def load_secrets(secrets_dir: str = "/run/secrets") -> Secrets:
    """Load secrets from Docker secrets or environment.
    
    Args:
        secrets_dir: Directory for Docker secrets (default: /run/secrets).
        
    Returns:
        Secrets: Validated secrets container.
        
    Raises:
        ValueError: If required secrets not found.
    """
    def _read_secret(name: str) -> Optional[str]:
        """Read secret from file or environment."""
        # Try Docker secret first
        secret_path = os.path.join(secrets_dir, name)
        if os.path.isfile(secret_path):
            try:
                with open(secret_path, "r") as f:
                    return f.read().strip()
            except (IOError, OSError):
                pass
        
        # Fallback to environment
        return os.environ.get(name.upper())
    
    api_key = _read_secret("api_key")
    api_secret = _read_secret("api_secret")
    dashboard_password = _read_secret("dashboard_password")
    
    if not api_key:
        raise ValueError(
            "api_key not found in Docker secrets or environment"
        )
    if not api_secret:
        raise ValueError(
            "api_secret not found in Docker secrets or environment"
        )
    if not dashboard_password:
        raise ValueError(
            "dashboard_password not found in Docker secrets or environment"
        )
    
    secrets = Secrets(
        api_key=api_key,
        api_secret=api_secret,
        dashboard_password=dashboard_password,
    )
    secrets.validate()
    return secrets
