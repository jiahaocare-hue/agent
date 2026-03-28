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
import sys
import json


def main():
    params = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
    
    input_content = params.get("input", "")
    
    if not input_content:
        print(json.dumps({"output": "", "error": "input 参数不能为空"}, ensure_ascii=False))
        return
    
    from langchain_openai import ChatOpenAI
    from config import settings
    
    llm = ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=0.0,
    )
    
    response = llm.invoke(input_content)
    
    result = {
        "output": response.content
    }
    
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
