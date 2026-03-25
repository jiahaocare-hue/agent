"""
知识库初始化脚本

使用方法:
    python init_knowledge_base.py

功能:
    扫描 knowledge_docs 目录下的所有 .txt 文件
    将每篇文章作为一个整体添加到向量数据库
"""
import os
from pathlib import Path
from vector_store import KnowledgeBaseStore
from config import settings
from logging_config import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def init_knowledge_base():
    """初始化知识库"""
    knowledge_store = KnowledgeBaseStore()
    
    docs_path = Path(settings.knowledge_base_path)
    if not docs_path.exists():
        logger.error(f"知识库目录不存在: {docs_path}")
        logger.info(f"请创建目录并放入文档文件: {docs_path}")
        return
    
    txt_files = list(docs_path.glob("*.txt"))
    if not txt_files:
        logger.warning(f"知识库目录中没有找到 .txt 文件: {docs_path}")
        return
    
    logger.info(f"找到 {len(txt_files)} 个文档文件")
    
    documents = []
    for txt_file in txt_files:
        try:
            content = txt_file.read_text(encoding="utf-8")
            title = txt_file.stem
            
            documents.append({
                "content": content,
                "title": title,
                "source_path": str(txt_file.absolute())
            })
            logger.info(f"读取文档: {title} ({len(content)} 字)")
        except Exception as e:
            logger.error(f"读取文件失败 {txt_file}: {e}")
    
    if documents:
        logger.info(f"开始添加 {len(documents)} 篇文档到知识库...")
        ids = knowledge_store.add_documents(documents)
        logger.info(f"成功添加 {len(ids)} 篇文档")
        logger.info(f"知识库现有文档总数: {knowledge_store.count()}")
    else:
        logger.warning("没有有效的文档需要添加")


def clear_knowledge_base():
    """清空知识库"""
    knowledge_store = KnowledgeBaseStore()
    logger.info(f"当前知识库文档数: {knowledge_store.count()}")
    knowledge_store.clear()
    logger.info("知识库已清空")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--clear":
        clear_knowledge_base()
    else:
        init_knowledge_base()
