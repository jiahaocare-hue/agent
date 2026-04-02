"""
通用的 LLM 处理脚本
接受输入内容，返回 LLM 的输出结果

调用方式：
python llm_process.py '{"input": "你的提示词或数据"}'

入参：
- input: string, 必填, 要发送给 LLM 的输入内容

出参：
- output: string, LLM 的输出结果
"""
import os
import sys
import json
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
LLM_BASE_URL = os.environ["LLM_BASE_URL"]
LLM_API_KEY = os.environ["LLM_API_KEY"]
LLM_MODEL = os.environ["LLM_MODEL"]
LLM_TEMPERATURE = os.environ["LLM_TEMPERATURE"]

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
    
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
    )
    
    response = llm.invoke(input_content)
    
    result = {
        "output": response.content
    }
    
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
