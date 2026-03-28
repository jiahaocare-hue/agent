"""
保存输出脚本
将当前输出保存到 md 文件，基于 input hash 定位文件

调用方式：
python save_output.py '{"input": "任务原始输入", "output_data": "要保存的内容"}'

入参：
- input: string, 必填, 任务的原始输入（用于计算 hash 定位文件）
- output_data: string, 必填, 要保存的输出内容

出参：
- success: boolean, 是否保存成功
"""
import sys
import json
import os
import hashlib


def main():
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    
    input_content = params.get("input", "")
    output_data = params.get("output_data", "")
    
    if not input_content:
        print(json.dumps({"success": False, "error": "input 参数不能为空"}, ensure_ascii=False))
        return
    
    input_hash = hashlib.md5(input_content.encode()).hexdigest()[:8]
    
    output_dir = os.path.join("data", "task_outputs")
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f"{input_hash}.md")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_data)
    
    result = {
        "success": True
    }
    
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
