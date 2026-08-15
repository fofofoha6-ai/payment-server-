import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Square Settings
    SQUARE_ACCESS_TOKEN = os.getenv('SQUARE_ACCESS_TOKEN')
    SQUARE_ENVIRONMENT = os.getenv('SQUARE_ENVIRONMENT', 'sandbox')
    SQUARE_LOCATION_ID = os.getenv('SQUARE_LOCATION_ID')
    SQUARE_APPLICATION_ID = os.getenv('SQUARE_APPLICATION_ID')
    SQUARE_WEBHOOK_SIGNATURE_KEY = os.getenv('SQUARE_WEBHOOK_SIGNATURE_KEY')
    
    # Server Settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'
    
    @staticmethod
    def get_square_environment():
        from square.client import Environment
        if Config.SQUARE_ENVIRONMENT == 'production':
            return Environment.PRODUCTION
        return Environment.SANDBOX