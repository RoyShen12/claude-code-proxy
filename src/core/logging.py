import logging
from src.core.config import config

def setup_logging():
    """Setup logging configuration."""
    # Logging Configuration
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper()),
        format='%(asctime)s - %(levelname)s - %(message)s',
    )
    
    # Configure uvicorn to be quieter
    for uvicorn_logger in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logging.getLogger(uvicorn_logger).setLevel(logging.WARNING)

# Initialize logging on import
setup_logging()
logger = logging.getLogger(__name__)