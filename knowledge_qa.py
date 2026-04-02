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
            SystemMessage(content="""你是一个知识问答助手。请根据提供的参考资料回答用户问题。

回答策略（按优先级执行）：
1. 【优先原文直出】如果参考资料中存在与用户问题高度相关的完整段落或定义，直接将该段原文作为答案输出，不要改写、总结或 paraphrase
2. 【标注来源】输出原文时必须保留文档来源信息，格式为：【来源：文档标题】（放在每段原文之前）
3. 【多段匹配】如果多个文档都包含与问题相关的信息，依次列出各段原文，每段独立标注来源
4. 【兜底整理】只有在没有直接匹配的原文段落时，才基于参考资料自行整理回答，但仍需标注来源

约束条件：
- 答案必须严格基于参考资料，禁止编造任何内容
- 如果参考资料中没有相关信息，请明确告知用户"知识库中未找到相关内容"
- summary 字段：生成约100字的摘要，概括本次问答的核心内容和答案要点；如果答案内容不足100字，summary 字段直接原样输出答案内容"""),
            HumanMessage(content=f"""参考资料：
{context}

用户问题：{question}

请按上述策略输出答案和摘要。""")
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
