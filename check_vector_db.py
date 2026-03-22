import chromadb
import json

client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_collection(name="successful_workflows")

data = collection.get()
print(f'Total workflows: {len(data["ids"])}')

if data['metadatas']:
    for i, metadata in enumerate(data['metadatas'][:5]):
        print(f'\nWorkflow {i+1}:')
        workflow = json.loads(metadata.get('workflow_json', '{}'))
        workflow_str = json.dumps(workflow, ensure_ascii=False)
        print(f'Contains route_key: {"route_key" in workflow_str}')
        print(workflow_str[:500])
else:
    print('Empty')
