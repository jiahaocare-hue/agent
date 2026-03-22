import chromadb
import json
import uuid
from typing import List, Optional, Dict


class WorkflowVectorStore:
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="successful_workflows",
            metadata={"hnsw:space": "cosine"}
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
