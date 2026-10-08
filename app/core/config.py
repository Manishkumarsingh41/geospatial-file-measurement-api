from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Geospatial File Measurement API"
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 50

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
