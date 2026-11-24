"""OpenAI-compatible 答案生成适配器。"""

import logging
import os

logger = logging.getLogger(__name__)


class OpenAICompatibleGenerator:
    def generate(self, question: str, context: str) -> str:
        try:
            from openai import OpenAI

            api_key = os.environ.get("DASHSCOPE_API_KEY", "")
            base_url = os.environ.get(
                "LLM_BASE_URL",
                "https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
            model_name = os.environ.get("LLM_MODEL", "qwen-plus")
            client = OpenAI(api_key=api_key, base_url=base_url)

            system_prompt = (
                "你是一个智能助手。请基于提供的【参考资料】回答用户的问题。\n"
                "如果参考资料为空或与问题无关，请忽略参考资料，利用你的通用知识进行回答，"
                "并在回答开头说明：'知识库中未找到相关内容，以下是基于通用知识的回答：'。\n"
                "回答要简洁、准确、有条理。"
            )
            user_prompt = f"问题：{question}\n\n"
            if context:
                user_prompt += f"【参考资料】：\n{context}"
            else:
                user_prompt += "【参考资料】：(无)"

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as exc:
            logger.error("LLM 生成失败: %s", exc)
            return "抱歉，生成回答时出现错误，请稍后再试。"
