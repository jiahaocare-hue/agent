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


def parse_args():
    """
    解析命令行参数，支持两种格式：
    1. JSON 格式：python script.py '{"input": "xxx"}'
    2. 命令行参数格式：python script.py --input xxx
    """
    if len(sys.argv) < 2:
        return {}
    
    first_arg = sys.argv[1]
    
    if first_arg.startswith('{'):
        try:
            return json.loads(first_arg)
        except json.JSONDecodeError:
            pass
    
    params = {}
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg.startswith('--'):
            key = arg[2:]
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith('--'):
                params[key] = sys.argv[i + 1]
                i += 2
            else:
                params[key] = True
                i += 1
        else:
            i += 1
    
    return params


def main():
    params = parse_args()
    
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
