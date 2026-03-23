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
