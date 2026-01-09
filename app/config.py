from pydantic import BaseModel

class Settings(BaseModel):
    db_url: str = "sqlite+aiosqlite:///./kisamore.db"
    scheduler_tick_seconds: int = 2

settings = Settings()
