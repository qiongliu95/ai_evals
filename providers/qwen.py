from .openai_compatible import ChatProvider

MODEL_ID = "qwen3.8-max-0902"
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class QwenProvider(ChatProvider):
    def __init__(self, base_url=BASE_URL, **kwargs):
        super().__init__(MODEL_ID, "DASHSCOPE_API_KEY", base_url, **kwargs)
