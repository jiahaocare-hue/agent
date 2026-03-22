from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any
import threading


@dataclass
class MCPFunction:
    """
    MCP 接口定义。
    
    Attributes:
        name: 接口名称
        description: 接口描述
        input_schema: 输入参数 schema，格式 {param_name: type_hint}
        output_schema: 输出参数 schema，格式 {param_name: type_hint}
        handler: 实际执行函数
        required_params: 必填参数列表
    """
    name: str
    description: str
    input_schema: Dict[str, str]
    output_schema: Dict[str, str]
    handler: Callable[..., Any]
    required_params: List[str] = field(default_factory=list)


def zoom_connect(meeting_id: str, password: str = None) -> dict:
    """
    连接 Zoom 会议。
    
    Args:
        meeting_id: 会议 ID（9-11 位数字）
        password: 会议密码（可选，通常是 10 位字符）
    
    Returns:
        连接结果字典，包含：
        - status: 连接状态（"connected" 或 "error"）
        - join_url: Zoom 会议链接
        - meeting_id: 会议 ID
    """
    join_url = f"zoommtg://zoom.us/join?confno={meeting_id}"
    if password:
        join_url += f"&pwd={password}"
    
    return {
        "status": "connected",
        "join_url": join_url,
        "meeting_id": meeting_id,
        "message": f"已准备好连接 Zoom 会议 {meeting_id}"
    }


def qq_meeting_connect(meeting_id: str) -> dict:
    """
    连接腾讯会议。
    
    Args:
        meeting_id: 会议 ID（通常是 10 位数字）
    
    Returns:
        连接结果字典，包含：
        - status: 连接状态（"connected" 或 "error"）
        - meeting_id: 会议 ID
        - message: 连接信息
    """
    return {
        "status": "connected",
        "meeting_id": meeting_id,
        "message": f"已准备好连接腾讯会议 {meeting_id}"
    }


class MCPManager:
    """
    MCP 模块管理器。
    
    职责：
    1. 注册 MCP 模块及其接口
    2. 查询模块可用接口
    3. 执行 MCP 接口调用
    
    注意：MCPManager 不管理权限，权限由 SubAgent 端控制。
    """
    
    _modules: Dict[str, Dict[str, MCPFunction]] = {}
    _lock = threading.Lock()
    
    @classmethod
    def register_module(cls, module_name: str, functions: Dict[str, MCPFunction]) -> None:
        """
        注册 MCP 模块。
        
        Args:
            module_name: 模块名称
            functions: 接口字典，格式 {function_name: MCPFunction}
        """
        with cls._lock:
            cls._modules[module_name] = functions
    
    @classmethod
    def get_module_functions(cls, module_names: List[str]) -> str:
        """
        查询多个模块的接口描述。
        
        Args:
            module_names: 模块名称列表
        
        Returns:
            格式化的接口描述文本
        """
        if not module_names:
            return "没有配置 MCP 模块"
        
        result_lines = ["# 可用的 MCP 接口\n"]
        
        for module_name in module_names:
            if module_name not in cls._modules:
                result_lines.append(f"## 模块: {module_name} (未注册)\n")
                continue
            
            result_lines.append(f"## 模块: {module_name}\n")
            
            for func_name, func in cls._modules[module_name].items():
                full_name = f"{module_name}.{func_name}"
                result_lines.append(f"### {full_name}")
                result_lines.append(f"描述: {func.description}")
                
                result_lines.append("入参:")
                for param, type_hint in func.input_schema.items():
                    req_mark = "必填" if param in func.required_params else "可选"
                    result_lines.append(f"  - {param} ({type_hint}, {req_mark})")
                
                result_lines.append("出参:")
                for param, type_hint in func.output_schema.items():
                    result_lines.append(f"  - {param} ({type_hint})")
                
                if func.required_params:
                    result_lines.append(f"\n**必填参数**: {', '.join(func.required_params)}")
                
                result_lines.append("")
        
        return "\n".join(result_lines)
    
    @classmethod
    def call(cls, module_name: str, function_name: str, kwargs: dict) -> dict:
        """
        执行 MCP 接口调用。
        
        Args:
            module_name: 模块名称
            function_name: 接口名称
            kwargs: 接口参数
        
        Returns:
            接口执行结果
        
        Raises:
            ValueError: 模块或接口不存在，或缺少必填参数
        """
        if module_name not in cls._modules:
            raise ValueError(f"未找到 MCP 模块: {module_name}")
        
        if function_name not in cls._modules[module_name]:
            raise ValueError(f"模块 {module_name} 中未找到接口: {function_name}")
        
        func = cls._modules[module_name][function_name]
        
        missing = [p for p in func.required_params if p not in kwargs]
        if missing:
            raise ValueError(f"缺少必填参数: {missing}")
        
        return func.handler(**kwargs)
    
    @classmethod
    def get_all_modules(cls) -> Dict[str, Dict[str, MCPFunction]]:
        """获取所有已注册的模块"""
        return cls._modules
    
    @classmethod
    def clear(cls) -> None:
        """清空所有已注册的模块"""
        with cls._lock:
            cls._modules = {}
    
    @classmethod
    def register_default_modules(cls) -> None:
        """
        注册默认的 MCP 模块。
        
        包含 connect_module（Zoom 会议和腾讯会议连接功能）。
        """
        cls.register_module("connect_module", {
            "zoom_connect": MCPFunction(
                name="zoom_connect",
                description="连接 Zoom 会议",
                input_schema={
                    "meeting_id": "string - 会议 ID（9-11 位数字）",
                    "password": "string - 会议密码"
                },
                output_schema={
                    "status": "string - 连接状态",
                    "join_url": "string - 加入链接",
                    "meeting_id": "string - 会议 ID"
                },
                handler=zoom_connect,
                required_params=["meeting_id"]
            ),
            "qq_meeting_connect": MCPFunction(
                name="qq_meeting_connect",
                description="连接腾讯会议",
                input_schema={
                    "meeting_id": "string - 会议 ID（通常是 10 位数字）"
                },
                output_schema={
                    "status": "string - 连接状态",
                    "meeting_id": "string - 会议 ID",
                    "message": "string - 连接信息"
                },
                handler=qq_meeting_connect,
                required_params=["meeting_id"]
            )
        })
