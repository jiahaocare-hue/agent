from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import Tuple
from logging_config import get_logger

logger = get_logger(__name__)


class KnowledgeAnswer(BaseModel):
    """知识问答答案结构化输出"""
    answer: str = Field(description="对用户问题的回答内容")
    summary: str = Field(description="约100字的摘要，概括本次问答的内容。如果答案不足100字，则原样输出答案内容")


class KnowledgeQAService:
    """知识库问答服务"""
    
    def __init__(self, vector_store, llm_model: str = None):
        """
        Args:
            vector_store: KnowledgeBaseStore 实例
            llm_model: 使用的模型名称，为空则使用默认模型
        """
        self.vector_store = vector_store
        
        from config import settings
        
        if llm_model:
            self.llm = ChatOpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=llm_model,
                temperature=0.1,
            )
        else:
            self.llm = ChatOpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key,
                model=settings.llm_model,
                temperature=0.1,
            )
        
        self.structured_llm = self.llm.with_structured_output(KnowledgeAnswer)
    
    def retrieve(self, question: str, top_k: int = 5) -> list:
        """检索相关文档
        
        Args:
            question: 用户问题
            top_k: 返回文档数量
        
        Returns:
            相关文档列表
        """
        logger.info(f"检索问题: {question}")
        documents = self.vector_store.search(question, n_results=top_k)
        logger.info(f"检索到 {len(documents)} 篇相关文档")
        return documents
    
    def generate_answer(self, question: str, documents: list) -> Tuple[str, str]:
        """生成答案和摘要
        
        Args:
            question: 用户问题
            documents: 相关文档列表，每个包含 content, title, source_path
        
        Returns:
            (答案, 摘要)
        """
        context = "\n\n---\n\n".join([
            f"【文档: {doc.get('title', '未知')}】\n{doc.get('content', '')}"
            for doc in documents
        ])
        
        messages = [
            SystemMessage(content="""你是一个知识问答助手。请严格根据提供的参考资料回答用户问题。

要求：
1. 答案必须基于参考资料，不要编造内容
2. 如果参考资料中没有相关信息，请明确告知用户
3. 回答要简洁准确
4. summary 字段需要生成约100字的摘要，概括本次问答的内容
5. 如果答案内容不足100字，summary 字段直接原样输出答案内容"""),
            HumanMessage(content=f"""参考资料：
{context}

用户问题：{question}

请回答问题并提供摘要。""")
        ]
        
        result = self.structured_llm.invoke(messages)
        
        return result.answer, result.summary
    
    def process_question(self, question: str, top_k: int = 5) -> Tuple[str, str]:
        """处理问题：检索 + 生成答案
        
        Args:
            question: 用户问题
            top_k: 检索文档数量
        
        Returns:
            (答案, 摘要)
        """
        documents = self.retrieve(question, top_k)
        
        if not documents:
            return "抱歉，知识库中没有找到相关内容。", "未找到相关内容。"
        
        return self.generate_answer(question, documents)
