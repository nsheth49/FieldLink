from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / '.env', extra='ignore')
    database_url: str = f'sqlite:///{ROOT / "fieldlink.db"}'
    session_secret: str = ''
    app_env: str = 'development'
    app_public_url: str = 'http://localhost:5173'
    ai_mode: str = 'mock'
    messaging_mode: str = 'mock'
    nvidia_api_key: str = ''
    nvidia_api_base: str = 'https://integrate.api.nvidia.com/v1'
    nvidia_model: str = 'nvidia/nemotron-3.5-lightning-30b-a3b'
    photon_api_key: str = ''
    photon_project_id: str = ''
    photon_sender_id: str = ''
    photon_webhook_secret: str = ''
    detector_leak_ratio: float = .03
    detector_degradation_ratio: float = .95

settings = Settings()
