import json
import traceback # 用于打印详细错误栈
from config import client, Config, logger
from prompts import SYSTEM_PROMPT
from tools import TOOL_MAP, TOOLS_SCHEMA

class ReActAgent:
    def __init__(self):
        # 现在的系统提示词不再需要包含复杂的工具格式说明，模型通过 tools 参数自动学习
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def _safe_json_parse(self, args_str):
        """增强版 JSON 解析：处理模型可能输出的 Markdown 代码块或非法字符"""
        try:
            # 去除可能存在的 Markdown 标签
            clean_str = args_str.strip()
            if clean_str.startswith("```json"):
                clean_str = clean_str.split("```json")[1].split("```")[0].strip()
            elif clean_str.startswith("```"):
                clean_str = clean_str.split("```")[1].split("```")[0].strip()
            return json.loads(clean_str)
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {args_str} | 错误: {e}")
            return None

    def run(self, user_query: str, max_turns: int = 5):
        self.messages.append({"role": "user", "content": user_query})
        
        for turn in range(max_turns):
            logger.info(f"开始第 {turn + 1} 轮思考...")
            
            # --- 核心修改：发送 tools 参数 ---
            try:
                response = client.chat.completions.create(
                    model=Config.MODEL,
                    messages=self.messages,
                    tools=TOOLS_SCHEMA,  # 这里的 schema 告诉模型它的能力
                    tool_choice="auto",
                    temperature=0
                )
            except Exception as e:
                logger.error(f"API 调用失败: {e}")
                return f"抱歉，在与模型通信时发生了错误：{e}"
            
            response_message = response.choices[0].message
            content = response_message.content
            tool_calls = response_message.tool_calls
            
            # 无论如何，先把模型的这个回复，包含 tool_calls 的 message 存入记忆
            self.messages.append(response_message)

            # 记录思考过程
            if content:
                logger.info(f"模型思考: \n{content}")
                
            # 如果模型给出了 Final Answer
            # 在 Function Calling 模式下，模型有时直接给出答案，不调用工具
            if content and "Final Answer:" in content:
                logger.info("任务完成，准备输出结果。")
                return content.split("Final Answer:")[-1].strip()

            # 如果模型决定调用工具
            if tool_calls:
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    raw_args = json.loads(tool_call.function.arguments)
                    tool_call_id = tool_call.id # 每个调用都有唯一 ID

                    # 增强型 JSON 解析
                    function_args = self._safe_json_parse(raw_args)

                    if function_args is None:
                        observation = "错误：工具参数格式非法，请确保输出标准的 JSON 格式。"
                    # 健壮的工具执行逻辑
                    else:
                        if function_name in TOOL_MAP:
                            logger.info(f"执行工具: {function_name} | 参数: {function_args}")
                            try:
                                # 执行工具并捕获业务逻辑错误
                                observation = TOOL_MAP[function_name](**function_args)
                            except Exception as e:
                                # 将错误回传给模型，让它尝试修复（例如改参数）
                                observation = f"工具执行过程中出错: {str(e)}"
                                logger.error(f"工具 {function_name} 崩溃: {traceback.format_exc()}")
                        else:
                            observation = f"错误：工具 {function_name} 不存在。"
                    
                    logger.info(f"工具返回结果: {observation}")

                    # 关键：把结果喂回给模型
                    # 必须包含 tool_call_id，角色必须是 "tool"
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "name": function_name,
                        "content": str(observation)
                    })
                
                # 执行完所有工具后，继续下一轮循环，让模型总结结果
                continue

            else:
                # 即使没有 Final Answer 标识，若没有 tool_calls 也视为回答结束
                return content if content else "未获取到有效回答。"
 
        return "思考达到上限，未能解决问题。"