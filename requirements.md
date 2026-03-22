# Windows Agent Framework 需求文档

## 一、功能性需求

### 1.1 任务管理

#### FR-001: 任务创建
系统 SHALL 支持根据用户输入创建任务。

**场景**：
- **WHEN** 用户输入任务描述
- **THEN** MainAgent 分析输入并返回 TaskDecision
- **AND** 系统创建任务记录到数据库

#### FR-002: 任务调度
系统 SHALL 支持一次性/周期性任务调度。

**场景**：
- **WHEN** 用户指定"每隔X分钟"、"每天X点"等调度语义
- **THEN** 系统创建 scheduled 状态任务
- **AND** TimerScheduler 在指定时间触发执行

#### FR-003: 任务取消
系统 SHALL 支持取消正在等待/运行的任务。

**场景**：
- **WHEN** 用户执行 `/cancel <task_id>`
- **THEN** 系统将任务标记为 cancelled
- **AND** 如果任务正在运行，GraphExecutor 检测状态安全退出

#### FR-004: 任务依赖
系统 SHALL 支持任务间依赖关系。

**场景**：
- **WHEN** 用户指定"先做A再做B"
- **THEN** 任务B创建时依赖任务A
- **AND** 任务B状态为 blocked，直到A完成

### 1.2 工作流管理

#### FR-005: 工作流生成
系统 SHALL 支持 SubAgent 生成工作流蓝图。

**场景**：
- **WHEN** 任务开始执行
- **THEN** SubAgent 调用 LLM 生成 WorkflowBlueprint
- **AND** 返回 can_handle、nodes、edges 等结构

#### FR-006: 工作流确认
系统 SHALL 在执行前请求用户确认。

**场景**：
- **WHEN** SubAgent 生成工作流后
- **THEN** 弹出 Tkinter 窗口显示工作流描述
- **AND** 用户确认后执行，修改后重新生成，或取消

#### FR-007: 工作流执行
系统 SHALL 支持顺序/并行/条件分支工作流。

**场景**：
- **WHEN** 用户确认工作流
- **THEN** GraphExecutor 构建并执行 StateGraph
- **AND** 支持工具调用、脚本执行、状态路由

#### FR-008: 工作流持久化
系统 SHALL 存储成功执行的工作流。

**场景**：
- **WHEN** 任务成功完成
- **AND** 工作流节点数 >= 2
- **THEN** VectorStore 存储工作流用于未来复用

### 1.3 技能管理

#### FR-009: 技能加载
系统 SHALL 从文件系统动态加载 Skills。

**场景**：
- **WHEN** 系统启动
- **THEN** SkillLoader 扫描 skills/ 目录
- **AND** 加载所有 skill.md 和依赖的脚本

#### FR-010: 子代理注册
系统 SHALL 支持 SubAgent 动态注册。

**场景**：
- **WHEN** 系统启动
- **THEN** SkillLoader 扫描 subagent_skills/ 目录
- **AND** AgentFactory 注册所有子代理类型

### 1.4 MCP 工具

#### FR-011: MCP 模块注册
系统 SHALL 支持 MCP 模块注册和调用。

**场景**：
- **WHEN** 系统启动
- **THEN** MCPManager.register_default_modules() 注册默认模块
- **AND** 提供 zoom_connect、qq_meeting_connect 等工具

#### FR-012: MCP 工具验证
系统 SHALL 验证工作流中的工具是否存在。

**场景**：
- **WHEN** SubAgent 生成工作流后
- **THEN** validate_workflow_resources() 验证所有工具
- **AND** 如果工具不存在，抛出错误

### 1.5 状态恢复

#### FR-013: 运行中任务恢复
系统 SHALL 在启动时恢复运行中的任务。

**场景**：
- **WHEN** 系统崩溃后重启
- **THEN** RecoveryManager.recover_all() 被调用
- **AND** 将 running 状态任务转为 pending

#### FR-014: 检查点恢复
系统 SHALL 支持工作流断点恢复。

**场景**：
- **WHEN** GraphExecutor.execute() 被调用
- **THEN** 首先检查是否存在检查点
- **AND** 如果存在，从检查点恢复执行

### 1.6 命令行接口

#### FR-015: 查询命令
系统 SHALL 支持通过命令查询任务状态。

**命令**：
- `/running` - 查看运行中任务
- `/pending` - 查看待执行任务
- `/completed` - 查看已完成任务
- `/scheduled` - 查看定时任务

#### FR-016: 控制命令
系统 SHALL 支持任务控制命令。

**命令**：
- `/cancel <id>` - 取消指定任务
- `/cancel all <status>` - 批量取消
- `/clear` - 清除 Agent 记忆
- `/reset-workflows` - 清空工作流案例库

---

## 二、非功能性需求

### 2.1 性能

#### NFR-001: 并发执行
系统 SHALL 支持最多 3 个任务并发执行（可配置）。

### 2.2 可靠性

#### NFR-002: 错误处理
系统 SHALL 捕获并记录工作流执行中的错误。

#### NFR-003: 状态一致性
系统 SHALL 保证任务状态在数据库和内存中一致。

### 2.3 可用性

#### NFR-004: 中文界面
系统 SHALL 提供中文的用户界面和错误消息。

#### NFR-005: 人工确认
系统 SHALL 在执行危险操作前请求用户确认。

### 2.4 可扩展性

#### NFR-006: 插件式技能
系统 SHALL 支持通过添加文件扩展技能，无需修改代码。

#### NFR-007: 插件式子代理
系统 SHALL 支持通过添加 markdown 文件扩展子代理。

---

## 三、用户故事

### US-001: 创建一次性任务
**AS A** 用户
**I WANT** 输入任务描述并立即执行
**SO THAT** 完成任务而不需要等待

### US-002: 创建定时任务
**AS A** 用户
**I WANT** 设置"每隔X分钟"或"每天X点"执行
**SO THAT** 自动完成周期性工作

### US-003: 取消错误任务
**AS A** 用户
**I WANT** 发现任务错误时取消
**SO THAT** 避免浪费资源

### US-004: 复用成功工作流
**AS A** 用户
**I WANT** 相同任务复用历史工作流
**SO THAT** 提高执行效率

### US-005: 扩展系统能力
**AS A** 开发者
**I WANT** 添加新的 Skills 和 SubAgents
**SO THAT** 扩展系统功能

---

## 四、验收标准

### AC-001: 任务创建和执行
- [ ] 用户输入"打印你好"能创建并执行任务
- [ ] 任务完成后状态变为 completed
- [ ] 输出显示任务结果

### AC-002: 定时任务
- [ ] 用户输入"每隔5分钟打印测试"能创建定时任务
- [ ] 5分钟后任务自动执行
- [ ] 后续每隔5分钟重复执行

### AC-003: 任务取消
- [ ] 用户执行 `/cancel <id>` 能取消 pending 任务
- [ ] 用户执行 `/cancel all pending` 能批量取消
- [ ] 取消后的任务状态为 cancelled

### AC-004: 工作流生成和确认
- [ ] SubAgent 能生成包含工具调用的工作流
- [ ] 执行前弹出确认窗口
- [ ] 用户可修改或取消

### AC-005: 技能加载
- [ ] 系统启动时加载所有 skills/
- [ ] 系统启动时加载所有 subagent_skills/
- [ ] list_available_agents 返回所有可用代理

### AC-006: 检查点恢复
- [ ] 工作流中断后重启能恢复执行
- [ ] 恢复后任务状态正确

### AC-007: 错误处理
- [ ] 脚本执行失败时返回有意义的错误消息
- [ ] 错误消息写入任务记录

---

## 五、术语表

| 术语 | 定义 |
|------|------|
| MainAgent | 主代理，负责用户意图理解和任务决策 |
| SubAgent | 子代理，负责生成具体工作流 |
| WorkflowBlueprint | 工作流蓝图，描述工作流的节点和边 |
| GraphExecutor | 图执行器，负责执行工作流 |
| Skill | 技能，描述特定能力的脚本和参数 |
| MCP | Model Control Protocol，工具调用协议 |
| Checkpoint | 检查点，用于断点恢复 |
| VectorStore | 向量存储，存储成功工作流用于复用 |
