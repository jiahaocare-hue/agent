from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from typing import Dict, Tuple, Any

load_dotenv()


CONFIG_SCHEMA: Dict[str, Dict[str, Any]] = {
    "llm_base_url": {"type": str, "description": "LLM API 地址"},
    "llm_api_key": {"type": str, "description": "LLM API 密钥", "sensitive": True},
    "llm_model": {"type": str, "description": "LLM 模型名称"},
    "llm_temperature": {"type": float, "description": "LLM 温度参数"},
    "max_workers": {"type": int, "description": "最大并发数"},
    "max_workflow_retries": {"type": int, "description": "工作流最大重试次数"},
    "log_level": {"type": str, "description": "日志级别"},
    "knowledge_top_k": {"type": int, "description": "知识库检索数量"},
}


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
    
    knowledge_base_path: str = "./knowledge_docs"
    knowledge_top_k: int = 5
    knowledge_llm_model: str = ""
    
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()


def get_config_schema() -> Dict[str, Dict[str, Any]]:
    """返回可配置项及其类型和描述"""
    return CONFIG_SCHEMA.copy()


def get_all_settings() -> Dict[str, Any]:
    """返回所有配置项及其当前值"""
    result = {}
    for key in CONFIG_SCHEMA:
        if hasattr(settings, key):
            result[key] = getattr(settings, key)
    return result


def update_setting(key: str, value: str) -> Tuple[bool, str]:
    """
    更新配置项并保存到 .env 文件
    
    Args:
        key: 配置项名称
        value: 新值（字符串形式）
    
    Returns:
        (success, message)
    """
    if key not in CONFIG_SCHEMA:
        available = ", ".join(CONFIG_SCHEMA.keys())
        return False, f"未知配置项: {key}\n可用的配置项: {available}"
    
    expected_type = CONFIG_SCHEMA[key]["type"]
    
    try:
        if expected_type == int:
            converted_value = int(value)
        elif expected_type == float:
            converted_value = float(value)
        elif expected_type == str:
            converted_value = value
        else:
            converted_value = value
    except ValueError:
        return False, f"类型转换失败: 期望 {expected_type.__name__} 类型，但值 '{value}' 无法转换"
    
    setattr(settings, key, converted_value)
    
    env_path = ".env"
    
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []
    
    env_key = key.upper()
    found = False
    new_lines = []
    
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(f"{env_key}=") or stripped.startswith(f"{env_key} ="):
            new_lines.append(f"{env_key}={value}\n")
            found = True
        else:
            new_lines.append(line)
    
    if not found:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines.append("\n")
        new_lines.append(f"{env_key}={value}\n")
    
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
    except Exception as e:
        return False, f"保存到 .env 文件失败: {str(e)}"
    
    return True, f"配置 '{key}' 已更新为 '{value}'"
