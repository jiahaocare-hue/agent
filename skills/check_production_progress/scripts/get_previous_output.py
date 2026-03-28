"""
获取上一次输出脚本
从 md 文件中读取上一次的输出，基于 input hash 定位文件

调用方式：
python get_previous_output.py '{"input": "任务原始输入"}'

入参：
- input: string, 必填, 任务的原始输入（用于计算 hash 定位文件）

出参：
- output: string, 上一次的输出内容，如果不存在则为空字符串
"""
import sys
import json
import os
import hashlib


def main():
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    
    input_content = params.get("input", "")
    
    if not input_content:
        print(json.dumps({"output": "", "error": "input 参数不能为空"}, ensure_ascii=False))
        return
    
    input_hash = hashlib.md5(input_content.encode()).hexdigest()[:8]
    
    output_dir = os.path.join("data", "task_outputs")
    output_file = os.path.join(output_dir, f"{input_hash}.md")
    
    previous_output = ""
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            previous_output = f.read().strip()
    
    result = {
        "output": previous_output
    }
    
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
