from dataclasses import dataclass
from typing import List, Dict


@dataclass
class WorkflowTemplate:
    name: str
    keywords: List[str]
    description: str
    workflow_json: Dict


PARALLEL_TEMPLATE = WorkflowTemplate(
    name="并行汇聚模式",
    keywords=["同时", "并行", "一起", "并发"],
    description="多个任务并行执行后汇聚结果",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我来并行执行这些任务",
        "description": "步骤1: 同时启动任务A和任务B\n步骤2: 等待两个任务都完成\n步骤3: 汇聚结果并返回",
        "nodes": [
            {
                "node_id": "task_a",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/task_a.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "task_b",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/task_b.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "merge",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/merge.py",
                    "args": ["{\"result_a\": \"${node_outputs.task_a.output}\", \"result_b\": \"${node_outputs.task_b.output}\"}"]
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "task_a", "is_conditional": False},
            {"source": "START", "target": "task_b", "is_conditional": False},
            {"source": "task_a", "target": "merge", "is_conditional": False},
            {"source": "task_b", "target": "merge", "is_conditional": False},
            {"source": "merge", "target": "END", "is_conditional": False}
        ]
    }
)


CONDITIONAL_TEMPLATE = WorkflowTemplate(
    name="条件分支模式",
    keywords=["如果", "判断", "条件", "根据"],
    description="根据条件选择不同的执行路径",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我会根据条件选择执行路径",
        "description": "步骤1: 执行判断任务\n步骤2: 根据结果选择分支\n步骤3: 执行对应分支的任务",
        "nodes": [
            {
                "node_id": "check_condition",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/check.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "branch_a",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/branch_a.py",
                    "args": []
                }
            },
            {
                "node_id": "branch_b",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/branch_b.py",
                    "args": []
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "check_condition", "is_conditional": False},
            {
                "source": "check_condition",
                "target": "branch_a",
                "is_conditional": True,
                "condition_variable": "node_outputs.check_condition.condition_met",
                "routing_map": {
                    "true": "branch_a",
                    "false": "branch_b"
                }
            },
            {"source": "branch_a", "target": "END", "is_conditional": False},
            {"source": "branch_b", "target": "END", "is_conditional": False}
        ]
    }
)


RETRY_TEMPLATE = WorkflowTemplate(
    name="循环重试模式",
    keywords=["重试", "失败后", "再次", "循环"],
    description="失败后自动重试",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我会执行任务并在失败时重试",
        "description": "步骤1: 执行任务\n步骤2: 如果失败则重试\n步骤3: 成功后返回结果",
        "nodes": [
            {
                "node_id": "main_task",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/main_task.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "retry_task",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/main_task.py",
                    "args": ["{\"input\": \"${input}\", \"retry\": \"true\"}"]
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "main_task", "is_conditional": False},
            {
                "source": "main_task",
                "target": "END",
                "is_conditional": True,
                "condition_variable": "node_outputs.main_task.success",
                "routing_map": {
                    "true": "END",
                    "false": "retry_task"
                }
            },
            {"source": "retry_task", "target": "END", "is_conditional": False}
        ]
    }
)


MULTI_STAGE_TEMPLATE = WorkflowTemplate(
    name="多阶段处理模式",
    keywords=["先", "然后", "接着", "最后", "依次"],
    description="多个阶段依次执行",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我会依次执行多个阶段",
        "description": "步骤1: 执行第一阶段\n步骤2: 执行第二阶段\n步骤3: 执行第三阶段\n步骤4: 返回最终结果",
        "nodes": [
            {
                "node_id": "stage1",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/stage1.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "stage2",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/stage2.py",
                    "args": ["{\"input\": \"${node_outputs.stage1.output}\"}"]
                }
            },
            {
                "node_id": "stage3",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/stage3.py",
                    "args": ["{\"input\": \"${node_outputs.stage2.output}\"}"]
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "stage1", "is_conditional": False},
            {"source": "stage1", "target": "stage2", "is_conditional": False},
            {"source": "stage2", "target": "stage3", "is_conditional": False},
            {"source": "stage3", "target": "END", "is_conditional": False}
        ]
    }
)


ERROR_HANDLER_TEMPLATE = WorkflowTemplate(
    name="错误处理模式",
    keywords=["失败", "错误", "异常", "出错"],
    description="包含错误处理节点",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我会执行任务并处理可能的错误",
        "description": "步骤1: 执行主任务\n步骤2: 如果出错则执行错误处理\n步骤3: 返回结果",
        "nodes": [
            {
                "node_id": "main_task",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/main_task.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "error_handler",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/error_handler.py",
                    "args": ["{\"error\": \"${node_outputs.main_task.error}\"}"]
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "main_task", "is_conditional": False},
            {
                "source": "main_task",
                "target": "END",
                "is_conditional": True,
                "condition_variable": "node_outputs.main_task.error",
                "routing_map": {
                    "false": "END",
                    "true": "error_handler"
                }
            },
            {"source": "error_handler", "target": "END", "is_conditional": False}
        ]
    }
)


SCATTER_GATHER_TEMPLATE = WorkflowTemplate(
    name="分发收集模式",
    keywords=["分发", "广播", "通知所有", "群发"],
    description="分发任务到多个节点，收集结果",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我会分发任务并收集结果",
        "description": "步骤1: 分发任务到多个节点\n步骤2: 各节点并行执行\n步骤3: 收集所有结果",
        "nodes": [
            {
                "node_id": "node_1",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/worker.py",
                    "args": ["{\"target\": \"target1\", \"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "node_2",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/worker.py",
                    "args": ["{\"target\": \"target2\", \"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "node_3",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/worker.py",
                    "args": ["{\"target\": \"target3\", \"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "gather",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/gather.py",
                    "args": ["{\"result1\": \"${node_outputs.node_1.output}\", \"result2\": \"${node_outputs.node_2.output}\", \"result3\": \"${node_outputs.node_3.output}\"}"]
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "node_1", "is_conditional": False},
            {"source": "START", "target": "node_2", "is_conditional": False},
            {"source": "START", "target": "node_3", "is_conditional": False},
            {"source": "node_1", "target": "gather", "is_conditional": False},
            {"source": "node_2", "target": "gather", "is_conditional": False},
            {"source": "node_3", "target": "gather", "is_conditional": False},
            {"source": "gather", "target": "END", "is_conditional": False}
        ]
    }
)


CASCADE_TEMPLATE = WorkflowTemplate(
    name="级联调用模式",
    keywords=["依次", "顺序", "步骤", "流程"],
    description="多个步骤依次执行",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我会依次执行这些步骤",
        "description": "步骤1: 执行第一步\n步骤2: 执行第二步\n步骤3: 执行第三步\n步骤4: 完成",
        "nodes": [
            {
                "node_id": "step1",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/step1.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "step2",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/step2.py",
                    "args": ["{\"input\": \"${node_outputs.step1.output}\"}"]
                }
            },
            {
                "node_id": "step3",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/step3.py",
                    "args": ["{\"input\": \"${node_outputs.step2.output}\"}"]
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "step1", "is_conditional": False},
            {"source": "step1", "target": "step2", "is_conditional": False},
            {"source": "step2", "target": "step3", "is_conditional": False},
            {"source": "step3", "target": "END", "is_conditional": False}
        ]
    }
)


RACING_TEMPLATE = WorkflowTemplate(
    name="并行竞速模式",
    keywords=["最快", "竞速", "任一", "第一个"],
    description="多个任务并行，取最快完成的结果",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我会并行执行并取最快的结果",
        "description": "步骤1: 同时启动多个任务\n步骤2: 使用第一个完成的结果\n步骤3: 忽略其他任务",
        "nodes": [
            {
                "node_id": "task_a",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/task_a.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "task_b",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/task_b.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "task_c",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/task_c.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "task_a", "is_conditional": False},
            {"source": "START", "target": "task_b", "is_conditional": False},
            {"source": "START", "target": "task_c", "is_conditional": False},
            {"source": "task_a", "target": "END", "is_conditional": False},
            {"source": "task_b", "target": "END", "is_conditional": False},
            {"source": "task_c", "target": "END", "is_conditional": False}
        ]
    }
)


STATE_MACHINE_TEMPLATE = WorkflowTemplate(
    name="状态机模式",
    keywords=["状态", "转换", "切换", "流转"],
    description="根据状态流转执行",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我会根据状态流转执行",
        "description": "步骤1: 检查当前状态\n步骤2: 根据状态执行对应操作\n步骤3: 更新状态",
        "nodes": [
            {
                "node_id": "check_state",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/check_state.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "state_a_handler",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/handler_a.py",
                    "args": []
                }
            },
            {
                "node_id": "state_b_handler",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/handler_b.py",
                    "args": []
                }
            },
            {
                "node_id": "state_c_handler",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/handler_c.py",
                    "args": []
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "check_state", "is_conditional": False},
            {
                "source": "check_state",
                "target": "state_a_handler",
                "is_conditional": True,
                "condition_variable": "node_outputs.check_state.state",
                "routing_map": {
                    "a": "state_a_handler",
                    "b": "state_b_handler",
                    "c": "state_c_handler"
                }
            },
            {"source": "state_a_handler", "target": "END", "is_conditional": False},
            {"source": "state_b_handler", "target": "END", "is_conditional": False},
            {"source": "state_c_handler", "target": "END", "is_conditional": False}
        ]
    }
)


FAN_OUT_FAN_IN_TEMPLATE = WorkflowTemplate(
    name="扇出扇入模式",
    keywords=["扇出", "扇入", "扩展", "收缩"],
    description="扇出执行后扇入汇聚",
    workflow_json={
        "can_handle": True,
        "reply_message": "好的，我会扇出执行后扇入汇聚",
        "description": "步骤1: 扇出到多个处理节点\n步骤2: 各节点并行处理\n步骤3: 扇入汇聚结果",
        "nodes": [
            {
                "node_id": "fan_out",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/fan_out.py",
                    "args": ["{\"input\": \"${input}\"}"]
                }
            },
            {
                "node_id": "worker_1",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/worker.py",
                    "args": ["{\"id\": \"1\", \"data\": \"${node_outputs.fan_out.data_1}\"}"]
                }
            },
            {
                "node_id": "worker_2",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/worker.py",
                    "args": ["{\"id\": \"2\", \"data\": \"${node_outputs.fan_out.data_2}\"}"]
                }
            },
            {
                "node_id": "fan_in",
                "action_type": "script",
                "script_action": {
                    "executable": "python",
                    "script_path": "/path/to/fan_in.py",
                    "args": ["{\"result1\": \"${node_outputs.worker_1.output}\", \"result2\": \"${node_outputs.worker_2.output}\"}"]
                }
            }
        ],
        "edges": [
            {"source": "START", "target": "fan_out", "is_conditional": False},
            {"source": "fan_out", "target": "worker_1", "is_conditional": False},
            {"source": "fan_out", "target": "worker_2", "is_conditional": False},
            {"source": "worker_1", "target": "fan_in", "is_conditional": False},
            {"source": "worker_2", "target": "fan_in", "is_conditional": False},
            {"source": "fan_in", "target": "END", "is_conditional": False}
        ]
    }
)


ALL_TEMPLATES = [
    PARALLEL_TEMPLATE,
    CONDITIONAL_TEMPLATE,
    RETRY_TEMPLATE,
    MULTI_STAGE_TEMPLATE,
    ERROR_HANDLER_TEMPLATE,
    SCATTER_GATHER_TEMPLATE,
    CASCADE_TEMPLATE,
    RACING_TEMPLATE,
    STATE_MACHINE_TEMPLATE,
    FAN_OUT_FAN_IN_TEMPLATE,
]


def get_relevant_examples(raw_input: str, limit: int = 2) -> List[Dict]:
    """
    根据用户输入的关键词，返回相关的工作流模板示例。
    
    Args:
        raw_input: 用户的原始输入文本
        limit: 返回的最大模板数量，默认为 2
        
    Returns:
        匹配的模板列表，每个模板包含 name, description, workflow_json
    """
    scored_templates = []
    
    for template in ALL_TEMPLATES:
        matched_count = 0
        for keyword in template.keywords:
            if keyword in raw_input:
                matched_count += 1
        
        if matched_count > 0:
            scored_templates.append({
                "name": template.name,
                "description": template.description,
                "workflow_json": template.workflow_json,
                "score": matched_count
            })
    
    if scored_templates:
        scored_templates.sort(key=lambda x: (-x["score"], ALL_TEMPLATES.index(
            next(t for t in ALL_TEMPLATES if t.name == x["name"])
        )))
        for t in scored_templates:
            del t["score"]
        return scored_templates[:limit]
    
    default_templates = [CASCADE_TEMPLATE, CONDITIONAL_TEMPLATE]
    return [
        {
            "name": t.name,
            "description": t.description,
            "workflow_json": t.workflow_json
        }
        for t in default_templates[:limit]
    ]
