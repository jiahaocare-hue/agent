import posthog
posthog.disabled = True
posthog.capture = lambda *args, **kwargs: None

import sqlite3
import os
from contextlib import ExitStack, closing
from datetime import datetime
from typing import List, Optional

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from config import settings
from database import TaskRepository
from engine import BackendEngine
from command_parser import CommandParser, CommandExecutor
from main_agent import MainAgent, TaskDecision, DirectResponse, TaskInfo, ScheduledInfo, KnowledgeQAResponse
from vector_store import KnowledgeBaseStore
from knowledge_qa import KnowledgeQAService
from subagent import initialize_skills, AgentFactory
from mcp_manager import MCPManager
from logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def _create_single_task(
    task_type: str,
    task_name: str,
    description: str,
    repo: TaskRepository,
    engine: BackendEngine,
    scheduled_info: Optional[ScheduledInfo] = None,
    dependencies: Optional[List[int]] = None,
) -> int:
    scheduled_at = None
    repeat_type = None
    repeat_config = None

    if scheduled_info:
        scheduled_at = scheduled_info.scheduled_at
        if scheduled_at is None:
            scheduled_at = datetime.now()
        repeat_type = scheduled_info.repeat_type
        if scheduled_info.repeat_config:
            repeat_config = scheduled_info.repeat_config.model_dump()

    if scheduled_at:
        task_id = repo.create_scheduled_task(
            task_type=task_type,
            task_name=task_name,
            raw_input=description,
            scheduled_at=scheduled_at,
            repeat_type=repeat_type,
            repeat_config=repeat_config,
            dependencies=dependencies,
        )
        engine.schedule_task(task_id, scheduled_at)
    else:
        task_id = repo.create_task(
            task_type=task_type,
            task_name=task_name,
            raw_input=description,
            dependencies=dependencies,
        )
    
    return task_id


def create_tasks_from_decision(
    decision: TaskDecision,
    repo: TaskRepository,
    engine: BackendEngine,
    raw_input: str,
) -> List[int]:
    created_task_ids = []

    if decision.is_single_task:
        task_id = _create_single_task(
            task_type=decision.task_type,
            task_name=decision.task_name,
            description=decision.description,
            repo=repo,
            engine=engine,
            scheduled_info=decision.scheduled_info,
        )
        created_task_ids.append(task_id)
    else:
        index_to_task_id = {}

        for i, task_info in enumerate(decision.tasks):
            real_deps = [
                index_to_task_id[idx] for idx in task_info.dependencies
            ]
            
            task_id = _create_single_task(
                task_type=task_info.task_type,
                task_name=task_info.task_name,
                description=task_info.description,
                repo=repo,
                engine=engine,
                scheduled_info=decision.scheduled_info,
                dependencies=real_deps,
            )
            index_to_task_id[i] = task_id
            created_task_ids.append(task_id)

    return created_task_ids


def main():
    if not settings.llm_api_key:
        raise ValueError("LLM_API_KEY 未配置，请在 .env 文件中设置")
    
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
    )
    repo = TaskRepository()
    
    MCPManager.register_default_modules()
    
    knowledge_store = KnowledgeBaseStore()
    knowledge_qa_service = KnowledgeQAService(
        vector_store=knowledge_store,
        llm_model=settings.knowledge_llm_model if settings.knowledge_llm_model else None
    )
    
    base_dir = os.path.dirname(__file__)
    skills_dir = os.path.join(base_dir, "skills")
    subagent_dir = os.path.join(base_dir, "subagent_skills")
    initialize_skills(skills_dir, subagent_dir)
    logger.info(f"Registered agents: {AgentFactory.get_available_types()}")

    custom_serde = JsonPlusSerializer(allowed_msgpack_modules=[
        ('main_agent', 'TaskDecision'),
        ('main_agent', 'DirectResponse'),
        ('main_agent', 'KnowledgeQAResponse')
    ])
    db_dir = os.path.dirname(settings.main_agent_checkpoint_db)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(settings.main_agent_checkpoint_db, check_same_thread=False)

    _stack = ExitStack()
    sqlite_conn = _stack.enter_context(
        closing(conn)
    )
    checkpointer = SqliteSaver(sqlite_conn, serde=custom_serde)
    main_agent = MainAgent(llm, checkpointer)
    
    engine = BackendEngine(max_workers=settings.max_workers)
    engine.start()

    parser = CommandParser()
    executor = CommandExecutor(engine)

    logger.info("Backend Engine started. Type 'exit' to quit.")
    logger.info("Type '/help' for available commands.\n")
    
    last_knowledge_summary = None

    try:
        while True:
            user_input = input("You: ")

            if not user_input.strip():
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                break

            if user_input.startswith("/"):
                parsed = parser.parse(user_input)
                if parsed.get("is_command"):
                    result = executor.execute(parsed)
                    print(result)
                    continue
                else:
                    logger.error(f"错误: {parsed.get('error', '无效命令')}")
                    continue

            try:
                if last_knowledge_summary:
                    enhanced_input = f"[上一轮知识问答摘要: {last_knowledge_summary}]\n\n用户输入: {user_input}"
                    response = main_agent.decide_with_logging(enhanced_input, thread_id="main-session")
                    last_knowledge_summary = None
                else:
                    response = main_agent.decide_with_logging(user_input, thread_id="main-session")
            except Exception as e:
                logger.error(f"主 Agent 决策失败: {e}")
                continue

            if isinstance(response, DirectResponse):
                logger.info(f"\n=== 直接响应 ===")
                logger.info(response.response)
                logger.info("=" * 30 + "\n")
                continue
            
            if isinstance(response, KnowledgeQAResponse):
                logger.info(f"\n=== 知识问答 ===")
                logger.info(f"问题: {response.question}")
                
                try:
                    answer, summary = knowledge_qa_service.process_question(
                        response.question,
                        top_k=settings.knowledge_top_k
                    )
                    logger.info(f"\n答案:\n{answer}")
                    logger.info("=" * 30 + "\n")
                    
                    last_knowledge_summary = summary
                except Exception as e:
                    logger.error(f"知识问答处理失败: {e}")
                continue

            decision = response

            logger.info(f"\n=== Task Decision ===")
            logger.info(f"Task Type: {decision.task_type}")
            logger.info(f"Task Name: {decision.task_name}")
            logger.info(f"Description: {decision.description}")
            logger.info(f"Is Single Task: {decision.is_single_task}")

            if decision.tasks:
                logger.info(f"Sub Tasks: {len(decision.tasks)}")
                for i, task in enumerate(decision.tasks):
                    logger.info(f"  [{i}] {task.task_name} ({task.task_type})")
                    logger.info(f"      Description: {task.description}")
                    logger.info(f"      Dependencies: {task.dependencies}")
            if decision.scheduled_info:
                logger.info(f"Scheduled: {decision.scheduled_info}")

            task_ids = create_tasks_from_decision(decision, repo, engine, user_input)
            logger.info(f"\nCreated Tasks: {task_ids}")

            engine.wakeup()
            logger.info(f"Engine Status: {engine.get_status()}")
            logger.info("=" * 30 + "\n")
    finally:
        _stack.close()
        logger.info("Stopping engine...")
        engine.stop()
        logger.info("Goodbye!")


if __name__ == "__main__":
    main()
