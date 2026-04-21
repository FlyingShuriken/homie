from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    glm_api_key: str = ""
    glm_model: str = "glm-4-flash"
    db_path: str = "./homie.db"
    demo_seed: bool = False
    max_listings_per_source: int = 25
    glm_orchestrator_max_iterations: int = 30
    glm_max_iterations: int = 10
    glm_retry_delay_seconds: int = 5
    scraper_request_delay_min: float = 1.0
    scraper_request_delay_max: float = 3.0
    log_level: str = "INFO"


settings = Settings()
