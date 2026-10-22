from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Refer & Earn Backend API"
    ENVIRONMENT: str = "development"
    DATABASE_URL: str = "mysql+pymysql://refer_user:refer_pass_123@127.0.0.1:3306/refer_earn"
    TEST_DATABASE_URL: str = "mysql+pymysql://refer_user:refer_pass_123@127.0.0.1:3306/refer_earn_test"
    JWT_SECRET_KEY: str = "super-secret-jwt-key-change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFERRAL_REWARD_POINTS: int = 100

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()