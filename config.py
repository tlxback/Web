from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    JWT_SECRET_KEY_FILE: str = "key.txt"
    
    @property
    def JWT_SECRET_KEY(self) -> str:
        with open(self.JWT_SECRET_KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

settings = Settings()