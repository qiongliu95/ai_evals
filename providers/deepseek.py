from .openai_compatible import ChatProvider

MODEL_ID = "deepseek-flash"
BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(ChatProvider):
    def __init__(self, base_url=BASE_URL, **kwargs):
        super().__init__(MODEL_ID, "DEEPSEEK_API_KEY", base_url, **kwargs)
