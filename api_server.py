from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any

app = FastAPI(title="Config API", description="配置管理 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/config")
def get_config() -> Dict[str, Any]:
    """获取所有配置"""
    from config import settings, CONFIG_SCHEMA
    
    config = {}
    for key, schema in CONFIG_SCHEMA.items():
        if hasattr(settings, key):
            value = getattr(settings, key)
            is_sensitive = schema.get("sensitive", False)
            
            config[key] = {
                "type": schema["type"].__name__,
                "description": schema.get("description", ""),
                "value": "******" if is_sensitive else value
            }
    
    return {
        "success": True,
        "config": config
    }


@app.post("/api/config")
def set_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """全量更新配置"""
    from config import update_settings_full
    
    success, message = update_settings_full(config)
    
    return {
        "success": success,
        "message": message
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
