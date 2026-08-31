# -*- coding: utf-8 -*-
"""
GUI ↔ LLM 桥接 (gui_llm_bridge.py)
- ChatEngine：优先调真实 LLM，失败/无 Key 自动降级为本地规则回复
- build_settings_dialog：⚙️ AI设置 弹窗
- start_streaming_reply：流式 token -> 通过 root.after() 调度到 Tkinter 主线程（线程安全）
本文件延迟 import tkinter，无 GUI 环境也可 import 与测试。
"""
import json
import os
import threading
import queue
from engine import AIConversation
from llm import LLMClient, load_llm_config


def _tk():
    """延迟导入 tkinter（仅真正构建 UI 时才需要）。"""
    import tkinter as tk
    return tk


class ChatEngine:
    """对话引擎：真实 LLM + 规则降级。"""
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.rule = AIConversation()
        self.client = LLMClient(load_llm_config(config_path))
        self.history = []

    def reply(self, user_text):
        """非流式兜底（GUI 主用 stream）。"""
        if self.client.is_available():
            try:
                text = self.client.reply(user_text, history=self.history[-10:])
                if text:
                    self.history.append({"role": "user", "content": user_text})
                    self.history.append({"role": "assistant", "content": text})
                    return text
            except Exception:
                pass
        return self.rule.reply(user_text)

    def stream_reply(self, user_text, on_token, on_done=None):
        """流式回复：token 通过 on_token 回调，完成后 on_done。线程安全由调用方保证。"""
        self.history.append({"role": "user", "content": user_text})
        if not self.client.is_available():
            # 无 Key：模拟打字机效果（规则回复）
            self._fake_stream(self.rule.reply(user_text), on_token, on_done)
            return
        buf = {"text": ""}
        try:
            self.client.reply(user_text, history=self.history[-10:], stream=True, on_token=on_token)
            # SDK 流式时 reply 返回 None，文本由 on_token 累积（调用方处理）
            if on_done:
                on_done()
        except Exception:
            fallback = self.rule.reply(user_text)
            self._fake_stream(fallback, on_token, on_done)

    def _fake_stream(self, text, on_token, on_done):
        """把一段文本拆成 token 逐个回调，模拟流式。"""
        tokens = text.split(" ")
        def push(i=0):
            if i >= len(tokens):
                if on_done:
                    on_done()
                return
            on_token(tokens[i] + " ")
            threading.Timer(0.03, lambda: push(i + 1)).start()
        push(0)


def start_streaming_reply(engine, user_text, display_widget, root,
                          placeholder="AI Tutor", history_callback=None):
    """
    在 GUI 中启动流式回复：
    - 在后台线程跑 LLM，避免阻塞 UI
    - token 通过 Queue + root.after() 投递到主线程，安全更新 Text 控件
    """
    q = queue.Queue()
    q.put(("start", ""))
    streamer = {"text": ""}

    def token_cb(delta):
        streamer["text"] += delta
        q.put(("token", delta))

    def run():
        try:
            engine.client.reply(user_text, history=engine.history[-10:], stream=True, on_token=token_cb)
        except Exception:
            q.put(("token", engine.rule.reply(user_text)))
        q.put(("done", ""))

    def drain():
        try:
            while True:
                tag, payload = q.get_nowait()
                if tag == "start":
                    display_widget.config(state="normal")
                    display_widget.insert("end", f"{placeholder}: ", "ai")
                elif tag == "token":
                    display_widget.insert("end", payload)
                    display_widget.see("end")
                elif tag == "done":
                    display_widget.insert("end", "\n\n")
                    display_widget.config(state="disabled")
                    if history_callback:
                        history_callback(streamer["text"])
                    break
        except queue.Empty:
            pass
        root.after(50, drain)

    threading.Thread(target=run, daemon=True).start()
    root.after(50, drain)


def build_settings_dialog(root, config_path="config.json"):
    """⚙️ AI设置 弹窗：选择 LLM 服务商 + 填 Key + 模型名。"""
    import tkinter as tk  # 仅真正构建 UI 时才需要 tkinter
    win = tk.Toplevel(root)
    win.title("⚙️ AI / LLM 设置")
    win.geometry("460x320")
    data = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    llm = data.setdefault("llm", {})
    tk.Label(win, text="选择大模型服务商：", font=("WenQuanYi Micro Hei", 11)).pack(anchor="w", padx=16, pady=(14, 2))
    provider_var = tk.StringVar(value=llm.get("provider", "openai"))
    pf = tk.Frame(win)
    pf.pack(fill="x", padx=16)
    for val, txt in [("openai", "OpenAI"), ("deepseek", "DeepSeek"), ("qwen", "通义千问"),
                     ("moonshot", "Kimi"), ("claude", "Claude"), ("tencent", "腾讯混元")]:
        tk.Radiobutton(pf, text=txt, variable=provider_var, value=val).pack(anchor="w", pady=1)

    tk.Label(win, text="API Key：", font=("WenQuanYi Micro Hei", 11)).pack(anchor="w", padx=16, pady=(10, 2))
    key_var = tk.StringVar(value=llm.get("api_key", ""))
    tk.Entry(win, textvariable=key_var, show="*", width=42).pack(padx=16, fill="x")
    tk.Label(win, text="模型名（可选，留空用默认）：", font=("WenQuanYi Micro Hei", 11)).pack(anchor="w", padx=16, pady=(8, 2))
    model_var = tk.StringVar(value=llm.get("model", ""))
    tk.Entry(win, textvariable=model_var, width=42).pack(padx=16, fill="x")

    status = tk.Label(win, text="", font=("WenQuanYi Micro Hei", 10), fg="#888")
    status.pack(pady=(10, 2))

    def save():
        llm["provider"] = provider_var.get()
        if key_var.get().strip():
            llm["api_key"] = key_var.get().strip()
        if model_var.get().strip():
            llm["model"] = model_var.get().strip()
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        status.config(text="✅ 已保存，下次对话生效", fg="#51cf66")

    tk.Button(win, text="💾 保存", font=("WenQuanYi Micro Hei", 12, "bold"),
              bg="#4a6cf7", fg="white", padx=24, pady=6, command=save).pack(pady=12)
    return win


__all__ = ["ChatEngine", "start_streaming_reply", "build_settings_dialog"]
