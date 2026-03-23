from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-4"
    llm_temperature: float = 0.0
    
    tasks_db_path: str = "data/tasks.db"
    checkpoint_db_path: str = "data/checkpoints.db"
    main_agent_checkpoint_db: str = "data/main_agent_checkpoint.db"
    chroma_db_path: str = "data/chroma_db"
    logs_dir: str = "data/logs"
    
    max_workers: int = 3
    scheduler_timeout: int = 5
    max_workflow_retries: int = 5
    embedding_model_path: str = ""
    
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
