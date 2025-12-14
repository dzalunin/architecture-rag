from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=True
    )
    
    LOG_LEVEL: str = Field('INFO', validate_default=False)

    # эмбеддинг
    EMBEDDING_MODEL: str = Field('intfloat/multilingual-e5-base', validate_default=False)
    EMBEDDING_MODELS_CACHE_DIR: str = Field('cache/models', validate_default=False)
    EMBEDDING_BATCH_SIZE: int = Field(16, validate_default=False)

    # faiss
    VECTORSTORE_DIR: str = Field('index', validate_default=False)

    # ollama
    OLLAMA_MODEL: str = Field('llama3', validate_default=False)
    OLLAMA_BASE_URL: str = Field('http://localhost:11434', validate_default=False) 
    OLLAMA_PULL_TIMEOUT: int = Field(600, validate_default=False)

    # retrieval
    SEARCH_TOP_K: int = Field(3, validate_default=False)

    SAVE_MODE: bool = Field(True, validate_default=False)

settings = Settings()
