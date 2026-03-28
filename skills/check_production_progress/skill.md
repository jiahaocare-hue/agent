# check_production_progress

## 能力描述
查询生产任务进度，与上一次查询结果对比，并将对比结果通知用户。

## 流程说明
1. 调用 `query_progress.py` 查询当前生产进度
2. 调用 `get_previous_output.py` 获取上一次的查询结果（基于 input hash）
3. 将当前结果、上一次结果、对比提示词发送给 LLM（使用 llm_process skill）
4. LLM 输出对比结果后，调用通知脚本发送给用户
5. 调用 `save_output.py` 保存当前结果供下次对比

## 依赖脚本
- query_progress.py: 查询生产进度
- get_previous_output.py: 获取上一次输出
- save_output.py: 保存当前输出

## 依赖 Skills
- llm_process: LLM 处理
- send_email: 发送通知

## 脚本说明

### query_progress.py
**功能**：查询生产进度

**入参**：无

**出参**：
| 字段 | 类型 | 描述 |
|------|------|------|
| output | string | 查询结果 |

**调用示例**：
```bash
python skills/check_production_progress/scripts/query_progress.py
```

**输出示例**：
```json
{"output": "{\"total_tasks\": 100, \"completed_tasks\": 75}"}
```

### get_previous_output.py
**功能**：获取上一次的输出

**入参**：
| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| input | string | 是 | 任务的原始输入（用于计算 hash 定位文件） |

**出参**：
| 字段 | 类型 | 描述 |
|------|------|------|
| output | string | 上一次的输出内容，如果不存在则为空字符串 |

**调用示例**：
```bash
python skills/check_production_progress/scripts/get_previous_output.py '{"input": "查询生产任务进度"}'
```

**输出示例**：
```json
{"output": "{\"total_tasks\": 100, \"completed_tasks\": 70}"}
```

### save_output.py
**功能**：保存当前输出

**入参**：
| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| input | string | 是 | 任务的原始输入（用于计算 hash 定位文件） |
| output_data | string | 是 | 要保存的输出内容 |

**出参**：
| 字段 | 类型 | 描述 |
|------|------|------|
| success | boolean | 是否保存成功 |

**调用示例**：
```bash
python skills/check_production_progress/scripts/save_output.py '{"input": "查询生产任务进度", "output_data": "{\"total_tasks\": 100, \"completed_tasks\": 75}"}'
```

**输出示例**：
```json
{"success": true}
```

## 对比提示词模板
请对比以下两次生产进度查询结果，并输出变化摘要：

**上一次结果：**
{{previous_output}}

**当前结果：**
{{current_output}}

请输出：
1. 主要变化摘要
2. 具体变化内容

## 输出
- 对比结果通知已发送给用户
