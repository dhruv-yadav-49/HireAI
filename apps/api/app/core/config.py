from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "HireAI"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True

    DATABASE_URL: str = ""
    DATABASE_URL_SYNC: str = ""

    SECRET_KEY: str = "dev_secret_key_placeholder"
    REFRESH_SECRET_KEY: str = "dev_refresh_secret_key_placeholder"
    ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    OPENAI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()