import posthog
posthog.disabled = True
posthog.capture = lambda *args, **kwargs: None

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
import json
import uuid
from pathlib import Path
from typing import List, Optional, Dict
from logging_config import get_logger

logger = get_logger(__name__)


class WorkflowVectorStore:
    def __init__(self, persist_directory: str = None, embedding_model_path: str = None):
        if persist_directory is None:
            from config import settings
            persist_directory = settings.chroma_db_path
            if embedding_model_path is None:
                embedding_model_path = settings.embedding_model_path
        
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        embedding_function = None
        if embedding_model_path:
            path = Path(embedding_model_path)
            if not path.is_absolute():
                path = Path(__file__).parent / path
            logger.info(f"Using local embedding model from: {path}")
            embedding_function = SentenceTransformerEmbeddingFunction(
                model_name=str(path)
            )
        
        self.collection = self.client.get_or_create_collection(
            name="successful_workflows",
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_function
        )
    
    def add_workflow(self, raw_input: str, workflow_json: dict, task_type: str, metadata: dict = None):
        """添加成功工作流到向量库"""
        self.collection.add(
            documents=[raw_input],
            metadatas=[{
                "task_type": task_type,
                "workflow_json": json.dumps(workflow_json, ensure_ascii=False),
                **(metadata or {})
            }],
            ids=[str(uuid.uuid4())]
        )
    
    def search_similar(self, query: str, task_type: str = None, n_results: int = 3) -> List[dict]:
        """检索语义相似的成功案例"""
        where_filter = None
        if task_type:
            where_filter = {"task_type": task_type}
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter
        )
        
        workflows = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i]
                workflows.append({
                    "raw_input": doc,
                    "workflow_json": json.loads(metadata['workflow_json']),
                    "task_type": metadata['task_type']
                })
        
        return workflows


class KnowledgeBaseStore:
    def __init__(self, persist_directory: str = None, embedding_model_path: str = None):
        if persist_directory is None:
            from config import settings
            persist_directory = settings.chroma_db_path
            if embedding_model_path is None:
                embedding_model_path = settings.embedding_model_path
        
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        embedding_function = None
        if embedding_model_path:
            path = Path(embedding_model_path)
            if not path.is_absolute():
                path = Path(__file__).parent / path
            logger.info(f"Using local embedding model from: {path}")
            embedding_function = SentenceTransformerEmbeddingFunction(
                model_name=str(path)
            )
        
        self.collection = self.client.get_or_create_collection(
            name="knowledge_base",
            metadata={"hnsw:space": "cosine"},
            embedding_function=embedding_function
        )
    
    def add_document(self, content: str, title: str, source_path: str) -> str:
        """添加单篇文档到知识库"""
        doc_id = str(uuid.uuid4())
        self.collection.add(
            documents=[content],
            metadatas=[{
                "title": title,
                "source_path": source_path,
            }],
            ids=[doc_id]
        )
        return doc_id
    
    def add_documents(self, documents: List[Dict[str, str]]) -> List[str]:
        """批量添加文档到知识库
        
        Args:
            documents: 文档列表，每个文档包含 content, title, source_path
        
        Returns:
            添加的文档 ID 列表
        """
        ids = [str(uuid.uuid4()) for _ in documents]
        self.collection.add(
            documents=[doc["content"] for doc in documents],
            metadatas=[{
                "title": doc["title"],
                "source_path": doc["source_path"],
            } for doc in documents],
            ids=ids
        )
        return ids
    
    def search(self, query: str, n_results: int = 5) -> List[dict]:
        """检索相关文档
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
        
        Returns:
            相关文档列表，每个包含 content, title, source_path
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        documents = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                metadata = results['metadatas'][0][i]
                documents.append({
                    "content": doc,
                    "title": metadata.get('title', ''),
                    "source_path": metadata.get('source_path', '')
                })
        
        return documents
    
    def count(self) -> int:
        return self.collection.count()
    
    def clear(self):
        self.client.delete_collection(name="knowledge_base")
        self.collection = self.client.get_or_create_collection(
            name="knowledge_base",
            metadata={"hnsw:space": "cosine"},
            embedding_function=self.collection._embedding_function
        )
