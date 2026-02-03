"""Flask web application configuration"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Flask configuration"""
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    API_BASE_URL = os.getenv('API_BASE_URL', 'http://localhost:8000')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
