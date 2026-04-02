"""
查询生产进度脚本
实际使用时需要根据具体的生产系统接口进行实现

调用方式：
python query_progress.py

入参：无

出参：
- output: string, 查询结果
"""
import sys
import json


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
    
    # TODO: 根据实际生产系统接口实现查询逻辑
    # 示例：模拟查询生产进度
    progress_data = {
        "total_tasks": 100,
        "completed_tasks": 75,
        "in_progress_tasks": 15,
        "pending_tasks": 10,
        "timestamp": "2024-01-15 10:30:00"
    }
    
    result = {
        "output": json.dumps(progress_data, ensure_ascii=False)
    }
    
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
