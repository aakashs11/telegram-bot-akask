"""
Runtime Secret Loader for GCP Secret Manager
Fetches secrets at application startup instead of environment variables
"""

import os
import logging
from typing import Optional
from google.cloud import secretmanager

logger = logging.getLogger(__name__)


class SecretLoader:
    """Load secrets from GCP Secret Manager at runtime"""
    
    def __init__(self, project_id: Optional[str] = None):
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.client = None
        self.is_production = os.getenv("K_SERVICE") is not None  # Cloud Run indicator
        
        if self.is_production and self.project_id:
            try:
                self.client = secretmanager.SecretManagerServiceClient()
                logger.info("Secret Manager client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Secret Manager: {e}")
    
    def get_secret(self, secret_name: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get secret from Secret Manager (production) or environment variable (dev)
        
        Args:
            secret_name: Name of the secret (e.g., 'telegram-bot-token')
            default: Default value if secret not found
            
        Returns:
            Secret value or default
        """
        # Development: use environment variables
        if not self.is_production:
            env_var = secret_name.upper().replace('-', '_')
            return os.getenv(env_var, default)
        
        # Production: fetch from Secret Manager
        if not self.client or not self.project_id:
            logger.warning(f"Secret Manager not available, using default for {secret_name}")
            return default
        
        try:
            name = f"projects/{self.project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("UTF-8")
            logger.debug(f"Loaded secret: {secret_name}")
            return secret_value
        except Exception as e:
            logger.error(f"Failed to load secret {secret_name}: {e}")
            return default


# Global instance
_secret_loader = None


def get_secret_loader() -> SecretLoader:
    """Get or create the global secret loader instance"""
    global _secret_loader
    if _secret_loader is None:
        _secret_loader = SecretLoader()
    return _secret_loader


def load_secret(secret_name: str, default: Optional[str] = None) -> Optional[str]:
    """Convenience function to load a secret"""
    return get_secret_loader().get_secret(secret_name, default)
