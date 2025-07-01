import os
import sys

# Configuration
class Config:
    def __init__(self):
        self.openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.openai_base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.azure_api_version = os.environ.get("AZURE_API_VERSION")  # For Azure OpenAI

        # Special handling for Azure OpenAI
        if self.azure_api_version:
            # If using Azure, ensure the base URL is properly formatted
            if '/openai/deployments/' in self.openai_base_url:
                # Extract the base endpoint from full deployment URL
                # e.g., https://roy-key-us-east-2.openai.azure.com/openai/deployments/gpt-4.1/chat/completions
                # becomes https://roy-key-us-east-2.openai.azure.com
                parts = self.openai_base_url.split('/openai/')
                if len(parts) > 1:
                    self.openai_base_url = parts[0]
                    print(f"Detected Azure OpenAI deployment URL, extracted endpoint: {self.openai_base_url}")

        self.host = os.environ.get("HOST", "0.0.0.0")
        self.port = int(os.environ.get("PORT", "8082"))
        self.log_level = os.environ.get("LOG_LEVEL", "INFO")
        self.max_tokens_limit = int(os.environ.get("MAX_TOKENS_LIMIT", "4096"))
        self.min_tokens_limit = int(os.environ.get("MIN_TOKENS_LIMIT", "100"))

        # Default max_tokens for downstream requests
        self.default_max_tokens = int(os.environ.get("DEFAULT_MAX_TOKENS", "1024"))

        # Connection settings
        self.request_timeout = int(os.environ.get("REQUEST_TIMEOUT", "90"))
        self.max_retries = int(os.environ.get("MAX_RETRIES", "2"))

        # Model settings - BIG and SMALL models
        self.big_model = os.environ.get("BIG_MODEL", "gpt-4o")
        self.small_model = os.environ.get("SMALL_MODEL", "gpt-4o-mini")

    def validate_api_key(self):
        """Basic API key validation"""
        if not self.openai_api_key:
            return False
        # Basic format check for OpenAI API keys
        if not self.openai_api_key.startswith('sk-'):
            return False
        return True

try:
    config = Config()
    print(f" Configuration loaded: API_KEY={'*' * 20}..., BASE_URL='{config.openai_base_url}'")
except Exception as e:
    print(f"=4 Configuration Error: {e}")
    sys.exit(1)
