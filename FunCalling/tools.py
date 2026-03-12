import re
from config import tavily

# --- 接入外部api ---
def google_search(query: str):
    """
    使用互联网搜索实时信息、新闻、百科等内容。
    """
    try:
        # search 接口会返回网页的标题、URL 和 核心内容摘要
        response = tavily.search(query=query, search_depth="advanced", max_results=3)
        
        # 将搜索结果格式化为简洁的字符串供模型阅读
        results = []
        for result in response['results']:
            results.append(f"来源: {result['url']}\n内容: {result['content']}")
        
        return "\n\n".join(results) if results else "未找到相关搜索结果。"
    except Exception as e:
        return f"搜索过程中发生错误: {str(e)}"
    

# --- 具体的执行代码 (业务实现) ---
def calculate(expression: str) -> str:
    """计算数学表达式，仅允许数字和基础算术符号"""
    try:
        # 只允许：数字、小数点、加减乘除、括号、空格
        if not re.match(r'^[0-9\+\-\*\/\(\)\.\s]+$', expression):
            return "错误：表达式包含非法字符，出于安全考虑已拦截。"
        
        # 使用 eval 之前已经通过正则过滤了恶意代码
        # 提示：更专业做法是使用 ast.literal_eval 或专用计算库
        result = eval(expression, {"__builtins__": None}, {})
        return str(result)
    except Exception as e:
        return f"数学计算出错: {str(e)}"
    

# --- 工具映射表 (方便 Engine 查找) ---
TOOL_MAP = {
    "google_search": google_search,
    "calculate": calculate,
}


# --- 工具说明书 (给 LLM 看的 Schema) ---
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "计算数学表达式的值。适用于加减乘除等基础数学运算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "要计算的数学表达式，例如：'12 * (3 + 5)'",
                    }
                },
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "google_search",
            "description": "当用户询问实时信息、新闻、历史事实、特定人物或需要查阅互联网资料时使用。输入应该是具体的搜索查询语句。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "优化后的搜索指令。必须遵循以下'全要素'原则：\n"
                            "1. 实体完整性：将代词（他、那里、该司）替换为具体的专有名词（如‘马斯克’、‘成都市’、‘苹果公司’）；\n"
                            "2. 上下文补全：若涉及特定背景，需加上前缀约束（如涉及中国则加‘中国...’，涉及编程则加‘Python...’）；\n"
                            "3. 意图显式化：在搜索词中加入目标动词（如‘对比’、‘最新进展’、‘官方定义’、‘实时数据’）；\n"
                            "4. 时间/空间锚点：自动补全当前的时间或相关的地理位置限制以消除歧义。\n"
                            "示例：用户说'查查他家今天的股价'，应转化为'特斯拉(Tesla)公司今日在纳斯达克的实时股价股票行情'。"
                        ),
                    }
                },
                "required": ["query"],
            },
        },
    }
]