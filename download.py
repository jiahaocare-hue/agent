import os

# 使用镜像站
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from sentence_transformers import SentenceTransformer

# 下载模型
print("Downloading model from hf-mirror.com...")
model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

# 保存到本地
save_path = "models/all-MiniLM-L6-v2"
print(f"Saving model to {save_path}...")
model.save(save_path)

print("Done!")