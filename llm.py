# -*- coding: utf-8 -*-
"""
大模型接入层 (llm.py)
支持：OpenAI / DeepSeek / 通义 / Moonshot / Claude + 任意 OpenAI 兼容服务。
优先官方 SDK，缺失自动降级为标准库 urllib 请求。
无 API Key 时调用方应降级为本地规则回复（见 gui_llm_bridge）。
"""
import os
import json
import threading


class LLMClient:
    def __init__(self, config=None):
        self.config = config or {}
        self.provider = (self.config.get("provider") or "openai").lower()
        self.api_key = self.config.get("api_key") or os.environ.get("OPENAI_API_KEY", "")
        self.model = self.config.get("model") or self._default_model()
        self.base_url = self.config.get("base_url") or self._default_base()
        self.temperature = self.config.get("temperature", 0.7)
        self.system_prompt = self.config.get("system_prompt", "You are a helpful English tutor.")
        self._sdk = self._try_import_sdk()

    def _default_model(self):
        return {"deepseek": "deepseek-chat", "moonshot": "moonshot-v1-8k",
                "qwen": "qwen-plus", "claude": "claude-3-sonnet"}.get(self.provider, "gpt-3.5-turbo")

    def _default_base(self):
        return {"deepseek": "https://api.deepseek.com/v1",
                "moonshot": "https://api.moonshot.cn/v1",
                "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "claude": "https://api.anthropic.com/v1"}.get(self.provider, "https://api.openai.com/v1")

    def _try_import_sdk(self):
        try:
            from openai import OpenAI
            return OpenAI
        except ImportError:
            return None

    def is_available(self):
        return bool(self.api_key)

    def reply(self, user_text, history=None, stream=False, on_token=None):
        """非流式：返回完整文本；流式：通过 on_token 回调，返回 None。"""
        if not self.is_available():
            return ""
        messages = [{"role": "system", "content": self.system_prompt}]
        for h in (history or []):
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": user_text})
        if self._sdk:
            return self._reply_sdk(messages, stream, on_token)
        return self._reply_urllib(messages, stream, on_token)

    def _reply_sdk(self, messages, stream, on_token):
        client = self._sdk(api_key=self.api_key, base_url=self.base_url)
        if stream:
            resp = client.chat.completions.create(model=self.model, messages=messages,
                                                   temperature=self.temperature, stream=True)
            for chunk in resp:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    on_token(delta)
            return None
        resp = client.chat.completions.create(model=self.model, messages=messages,
                                               temperature=self.temperature)
        return resp.choices[0].message.content or ""

    def _reply_urllib(self, messages, stream, on_token):
        import urllib.request
        url = self.base_url.rstrip("/") + "/chat/completions"
        body = json.dumps({"model": self.model, "messages": messages,
                           "temperature": self.temperature, "stream": bool(stream)}).encode()
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")
        if stream:
            # 简易 SSE：逐行读取 data: {...}
            with urllib.request.urlopen(req, timeout=30) as r:
                for line in r:
                    line = line.decode().strip()
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        try:
                            delta = json.loads(data)["choices"][0]["delta"].get("content", "")
                            if delta:
                                on_token(delta)
                        except Exception:
                            continue
            return None
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())["choices"][0]["message"]["content"]


def load_llm_config(path="config.json"):
    """从 config.json 的 [llm] 段加载配置。"""
    cfg = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                cfg = json.load(f).get("llm", {})
        except Exception:
            cfg = {}
    return cfg


__all__ = ["LLMClient", "load_llm_config"]
