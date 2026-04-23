from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=False, extra="ignore"
    )

    glm_api_key: str = ""
    glm_model: str = "claude-3-5-sonnet-20241022"
    glm_base_url: str = "https://api.ilmu.ai/v1"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/homie"
    demo_seed: bool = False
    max_listings_per_source: int = 25
    glm_orchestrator_max_iterations: int = 30
    glm_max_iterations: int = 10
    glm_retry_delay_seconds: int = 5
    scraper_request_delay_min: float = 1.0
    scraper_request_delay_max: float = 3.0
    log_level: str = "INFO"


settings = Settings()
