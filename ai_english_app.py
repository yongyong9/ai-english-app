# -*- coding: utf-8 -*-
"""
AI 学英语 App (English Learner)
一个基于 Tkinter 的桌面英语学习应用，包含：
1. 单词卡片学习 (Spaced Repetition 简易版)
2. AI 对话练习 (基于内置规则模拟 AI 反馈)
3. 发音跟读评分 (基于录音能量分析模拟打分)
4. 智能测验 (选择题 + 填空题)
5. 学习统计与连续打卡
数据本地存储在 learning_data.json
"""

import os
import json
import random
import datetime
import hashlib
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from collections import defaultdict

try:
    import pyaudio
    import wave
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False

try:
    import asr as asr_module
    from asr import PronunciationScorer
    HAS_ASR = True
except ImportError:
    HAS_ASR = False

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learning_data.json")

# ----------------------------- 词库（内置） -----------------------------
BUILTIN_WORDS = [
    {"word": "serendipity", "pos": "n.", "meaning": "意外发现美好事物的运气", "example": "Finding this café was pure serendipity."},
    {"word": "eloquent", "pos": "adj.", "meaning": "雄辩的，有口才的", "example": "She made an eloquent speech."},
    {"word": "resilient", "pos": "adj.", "meaning": "有韧性的，能迅速恢复的", "example": "Children are remarkably resilient."},
    {"word": "ambiguous", "pos": "adj.", "meaning": "含糊不清的，有歧义的", "example": "The ending of the story is ambiguous."},
    {"word": "meticulous", "pos": "adj.", "meaning": "一丝不苟的，细致的", "example": "He kept meticulous notes."},
    {"word": "pragmatic", "pos": "adj.", "meaning": "务实的，实用的", "example": "We need a pragmatic solution."},
    {"word": "ephemeral", "pos": "adj.", "meaning": "短暂的，朝生暮死的", "example": "Fame is often ephemeral."},
    {"word": "benevolent", "pos": "adj.", "meaning": "仁慈的，乐善好施的", "example": "A benevolent smile lit his face."},
    {"word": "skeptical", "pos": "adj.", "meaning": "怀疑的，持怀疑态度的", "example": "I'm skeptical about his claims."},
    {"word": "versatile", "pos": "adj.", "meaning": "多才多艺的，多功能的", "example": "This is a versatile tool."},
    {"word": "diligent", "pos": "adj.", "meaning": "勤勉的，用功的", "example": "She is a diligent student."},
    {"word": "gregarious", "pos": "adj.", "meaning": "爱交际的，群居的", "example": "He is a gregarious person."},
    {"word": "lucid", "pos": "adj.", "meaning": "清晰的，易懂的", "example": "She gave a lucid explanation."},
    {"word": "nostalgia", "pos": "n.", "meaning": "怀旧，乡愁", "example": "The photo filled her with nostalgia."},
    {"word": "obsolete", "pos": "adj.", "meaning": "过时的，废弃的", "example": "Typewriters are now obsolete."},
]

# ----------------------------- 数据管理 -----------------------------
class DataStore:
    def __init__(self):
        self.data = self._load()

    def _load(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default()

    def _default(self):
        return {
            "words": {},        # word -> {"level": 0-5, "next_review": "YYYY-MM-DD", "correct":0, "wrong":0}
            "quiz_history": [], # [{"date":..., "score":..., "total":...}]
            "streak": 0,
            "last_day": None,
            "total_study_minutes": 0,
            "chat_log": [],
        }

    def save(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def ensure_words(self):
        today = datetime.date.today().isoformat()
        for w in BUILTIN_WORDS:
            if w["word"] not in self.data["words"]:
                self.data["words"][w["word"]] = {
                    "level": 0, "next_review": today, "correct": 0, "wrong": 0
                }
        self.save()

    def record_review(self, word, correct):
        w = self.data["words"].get(word)
        if not w:
            return
        if correct:
            w["correct"] += 1
            w["level"] = min(5, w["level"] + 1)
        else:
            w["wrong"] += 1
            w["level"] = max(0, w["level"] - 1)
        # 间隔重复：level 越高，复习间隔越长
        interval_days = [0, 1, 3, 7, 14, 30][w["level"]]
        next_date = datetime.date.today() + datetime.timedelta(days=interval_days)
        w["next_review"] = next_date.isoformat()
        self.save()

    def due_words(self):
        today = datetime.date.today().isoformat()
        return [w for w in BUILTIN_WORDS
                if self.data["words"].get(w["word"], {}).get("next_review", today) <= today]

    def update_streak(self):
        today = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        if self.data["last_day"] == today:
            return
        if self.data["last_day"] == yesterday:
            self.data["streak"] += 1
        elif self.data["last_day"] != today:
            self.data["streak"] = 1
        self.data["last_day"] = today
        self.save()


# ----------------------------- AI 对话引擎（规则模拟） -----------------------------
class AIConversation:
    """用规则 + 模板模拟 AI 外教反馈。真实产品可替换为 OpenAI API 等。"""
    def __init__(self):
        self.templates = {
            "greeting": [
                "Hi there! 👋 How are you doing today?",
                "Hello! 😊 What would you like to talk about?",
                "Hey! Great to see you. How's your day?",
            ],
            "question": [
                "That's interesting! Can you tell me more about that?",
                "I see. What do you think is the main reason?",
                "Nice! Could you give me an example from your own life?",
            ],
            "encourage": [
                "You're doing great! 🌟 Keep going!",
                "I love your enthusiasm! 💪",
                "Excellent progress! 👏",
            ],
            "correction": [
                "Good try! A more natural way to say that would be: \"{suggestion}\".",
                "Almost there! You could also say: \"{suggestion}\".",
            ],
            "fallback": [
                "That's a great point! Tell me more.",
                "I understand. How does that make you feel?",
                "Interesting! Why do you think that is?",
            ],
        }
        # 简单错误模式 -> 建议
        self.corrections = [
            (["i am", "i'm"], "I am", "remember to capitalize 'I' in English."),
            (["dont", "dont"], "don't", "use the apostrophe: don't."),
            (["very good", "very nice"], None, "try a stronger adjective like 'fantastic' or 'wonderful' for variety."),
            (["maybe"], None, "try 'perhaps' or 'possibly' to sound more formal."),
        ]

    def reply(self, user_text):
        text = (user_text or "").strip().lower()
        if not text:
            return random.choice(self.templates["greeting"])
        # 检测改进点
        for keywords, suggestion, tip in self.corrections:
            for kw in keywords:
                if kw in text:
                    if suggestion:
                        return f"Good try! A more natural way: \"{suggestion}\". ({tip})"
                    else:
                        return f"Nice! Tip: {tip}"
        # 根据内容给不同回应
        if any(w in text for w in ["hello", "hi", "hey"]):
            return random.choice(self.templates["greeting"])
        if "?" in user_text:
            return random.choice(self.templates["question"])
        if any(w in text for w in ["thank", "thanks"]):
            return "You're very welcome! 😊 Anything else?"
        if any(w in text for w in ["bad", "sad", "tired", "stress"]):
            return "I'm sorry to hear that. 💙 Taking breaks helps — want to try a fun word game?"
        if any(w in text for w in ["happy", "good", "great", "love"]):
            return random.choice(self.templates["encourage"])
        return random.choice(self.templates["fallback"])


# ----------------------------- 主应用 -----------------------------
class EnglishApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("AI 学英语 English Learner")
        self.geometry("960x680")
        self.configure(bg="#f4f7fb")
        self.wordbook = WordBook()
        self.store = DataStore(wordbook=self.wordbook)
        self.store.ensure_words()
        self.ai = AIConversation()
        self._chat_engine = None  # 懒加载：首次进入 AI 对话页时构建
        # ASR 发音打分器（配置从 config.json 的 [asr] 段读取；无 Key 自动离线降级）
        self.asr_config = asr_module.ASRConfig() if HAS_ASR else None
        self.scorer = PronunciationScorer(config=self.asr_config) if HAS_ASR else None
        self._recording = False
        self._audio_frames = []
        self._pyaudio = None
        self._stream = None

        self._build_ui()
        self.store.update_streak()
        self._refresh_stats()
        self._show_due_count()

    # -------------------- UI 布局 --------------------
    def _build_ui(self):
        # 顶部标题栏
        header = tk.Frame(self, bg="#4a6cf7", height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="🤖 AI 学英语", font=("WenQuanYi Micro Hei", 20, "bold"),
                 fg="white", bg="#4a6cf7").pack(side="left", padx=20)
        self.streak_label = tk.Label(header, text="🔥 连续 0 天", font=("WenQuanYi Micro Hei", 12),
                                     fg="white", bg="#4a6cf7")
        self.streak_label.pack(side="right", padx=20)

        # 侧边导航
        nav = tk.Frame(self, bg="#eef2fb", width=180)
        nav.pack(side="left", fill="y")
        nav.pack_propagate(False)

        self.pages = {}
        container = tk.Frame(self, bg="#f4f7fb")
        container.pack(side="left", fill="both", expand=True)

        pages_conf = [
            ("📖 单词学习", self._page_flashcard),
            ("💬 AI 对话", self._page_chat),
            ("🎙️ 跟读练习", self._page_pronunciation),
            ("📝 智能测验", self._page_quiz),
            ("📊 学习统计", self._page_stats),
        ]
        for name, builder in pages_conf:
            btn = tk.Button(nav, text=name, font=("WenQuanYi Micro Hei", 13),
                            bg="#eef2fb", fg="#333", bd=0, anchor="w", padx=20, pady=12,
                            activebackground="#dbe4fb", cursor="hand2",
                            command=lambda b=builder: self._switch_page(b))
            btn.pack(fill="x")
            frame = tk.Frame(container, bg="#f4f7fb")
            self.pages[builder] = frame
            b(frame)

        self._switch_page(self._page_flashcard)

    def _switch_page(self, builder):
        for f in self.pages.values():
            f.pack_forget()
        self.pages[builder].pack(fill="both", expand=True)
        self._current_page_builder = builder
        # 刷新动态内容
        if builder == self._page_stats:
            self._refresh_stats()
        elif builder == self._page_flashcard:
            self._show_due_count()

    # ---------------- 通用工具 ----------------
    def _big_label(self, parent, text, size=28, color="#222"):
        return tk.Label(parent, text=text, font=("WenQuanYi Micro Hei", size, "bold"),
                        fg=color, bg="#f4f7fb")

    # ==================== 1. 单词学习 ====================
    def _page_flashcard(self, parent):
        center = tk.Frame(parent, bg="#f4f7fb")
        center.pack(expand=True, fill="both", padx=40, pady=20)

        # 顶部工具条：导入词库 + 词库信息
        toolbar = tk.Frame(center, bg="#f4f7fb")
        toolbar.pack(fill="x", pady=(0, 10))
        tk.Button(toolbar, text="📥 导入词库", font=("WenQuanYi Micro Hei", 11, "bold"),
                  bg="#4a6cf7", fg="white", padx=16, pady=6, bd=0,
                  command=self._import_words).pack(side="left")
        tk.Button(toolbar, text="❓ 格式说明", font=("WenQuanYi Micro Hei", 10),
                  bg="#eef2fb", fg="#4a6cf7", padx=12, pady=6, bd=0,
                  command=self._show_import_help).pack(side="left", padx=(8, 0))
        self.book_info_label = tk.Label(toolbar, text="", font=("WenQuanYi Micro Hei", 10),
                                        fg="#888", bg="#f4f7fb")
        self.book_info_label.pack(side="right")
        self._refresh_book_info()

        self.card_frame = tk.Frame(center, bg="white", highlightbackground="#4a6cf7",
                                   highlightthickness=2, width=520, height=300)
        self.card_frame.pack(pady=20)
        self.card_frame.pack_propagate(False)

        self.card_word = self._big_label(self.card_frame, "", 34, "#4a6cf7")
        self.card_word.pack(pady=(30, 5))
        self.card_pos = tk.Label(self.card_frame, text="", font=("WenQuanYi Micro Hei", 14),
                                 fg="#888", bg="white")
        self.card_pos.pack()
        self.card_meaning = tk.Label(self.card_frame, text="点击开始学习", font=("WenQuanYi Micro Hei", 18),
                                     fg="#333", bg="white")
        self.card_meaning.pack(pady=10)
        self.card_example = tk.Label(self.card_frame, text="", font=("WenQuanYi Micro Hei", 12),
                                     fg="#666", bg="white", wraplength=460)
        self.card_example.pack(pady=(5, 20))

        self.card_reveal_btn = tk.Button(center, text="👁️ 显示答案", font=("WenQuanYi Micro Hei", 12),
                                          bg="#4a6cf7", fg="white", padx=20, pady=8, bd=0,
                                          command=self._reveal_card)
        self.card_reveal_btn.pack()

        btns = tk.Frame(center, bg="#f4f7fb")
        btns.pack(pady=15)
        tk.Button(btns, text="❌ 不认识", font=("WenQuanYi Micro Hei", 12), bg="#ff6b6b", fg="white",
                  padx=18, pady=8, bd=0, command=lambda: self._answer_card(False)).pack(side="left", padx=10)
        tk.Button(btns, text="✅ 认识", font=("WenQuanYi Micro Hei", 12), bg="#51cf66", fg="white",
                  padx=18, pady=8, bd=0, command=lambda: self._answer_card(True)).pack(side="left", padx=10)

        self.card_queue = []
        self.card_idx = 0

    def _show_due_count(self):
        due = self.store.due_words()
        self.card_meaning.config(text=f"今日待复习单词：{len(due)} 个\n点击「开始学习」进入")

    # ---------------- 词库导入 ----------------
    def _refresh_book_info(self):
        total = len(self.wordbook.all_words())
        custom = self.wordbook.custom_count()
        if hasattr(self, "book_info_label"):
            self.book_info_label.config(text=f"词库共 {total} 词（自定义 {custom}）")

    def _show_import_help(self):
        help_text = (
            "支持导入的文件格式（字段名中英文皆可）：\n\n"
            "1) JSON：对象数组\n"
            '   [{"word":"ubiquitous","pos":"adj.","meaning":"无处不在的","example":"..."}]\n\n'
            "2) CSV / TSV：首行为表头\n"
            '   word,pos,meaning,example  或  单词,词性,释义,例句\n\n'
            "3) TXT：一行一个，支持以下写法\n"
            "   ubiquitous 无处不在的\n"
            "   ubiquitous,adj.,无处不在的,例句...\n\n"
            "说明：\n"
            "  • word（单词）为必填，其余可选；重复单词自动去重。\n"
            "  • 导入后自定义词与内置词合并，可立即用于学习 / 测验。\n"
            "  • 导入模式可选「追加」或「替换」自定义词库。"
        )
        win = tk.Toplevel(self)
        win.title("📥 词库导入格式说明")
        win.geometry("560x420")
        txt = tk.Text(win, font=("WenQuanYi Micro Hei", 11), wrap="word", padx=14, pady=14)
        txt.pack(fill="both", expand=True)
        txt.insert("1.0", help_text)
        txt.config(state="disabled")

    def _import_words(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="选择词库文件",
            filetypes=[("支持的文件", "*.csv *.tsv *.json *.txt"),
                       ("CSV", "*.csv"), ("TSV", "*.tsv"),
                       ("JSON", "*.json"), ("文本", "*.txt")])
        if not path:
            return
        # 选择导入模式
        mode = messagebox.askquestion(
            "导入模式",
            "「是」= 追加到现有自定义词库\n「否」= 替换为新词库（清空原有自定义词）\n\n"
            "内置词库始终保留，不会被清除。",
            type="yesno")
        mode = "replace" if mode == "no" else "append"
        try:
            added, failed = self.wordbook.add_from_file(path, mode=mode)
        except Exception as e:
            messagebox.showerror("导入失败", str(e))
            return
        # 导入后为新词建立复习记录
        self.store.ensure_words()
        msg = f"成功导入 {added} 个新单词！"
        if failed:
            msg += f"\n\n以下 {len(failed)} 条跳过：\n" + "\n".join(
                f"  · {w or '(空)'}：{reason}" for w, reason in failed[:10])
        messagebox.showinfo("导入完成", msg)
        self._refresh_book_info()
        self._show_due_count()

    def _reveal_card(self):
        due = self.store.due_words()
        if not due:
            due = BUILTIN_WORDS
        self.card_queue = due[:]
        random.shuffle(self.card_queue)
        self.card_idx = 0
        self._render_card()

    def _render_card(self):
        if self.card_idx >= len(self.card_queue):
            self.card_word.config(text="🎉 完成！")
            self.card_pos.config(text="")
            self.card_meaning.config(text=f"本轮复习完成，共 {len(self.card_queue)} 词")
            self.card_example.config(text="")
            return
        w = self.card_queue[self.card_idx]
        self.card_word.config(text=w["word"])
        self.card_pos.config(text=w["pos"])
        self.card_meaning.config(text="？？？")
        self.card_example.config(text="")

    def _answer_card(self, correct):
        if self.card_idx >= len(self.card_queue):
            return
        w = self.card_queue[self.card_idx]
        # 先显示答案
        self.card_meaning.config(text=w["meaning"])
        self.card_example.config(text="🗣️ " + w["example"])
        self.store.record_review(w["word"], correct)
        self.card_idx += 1
        self.after(1200, self._render_card)

    # ==================== 2. AI 对话（真实 LLM + 流式 + 降级） ====================
    def _get_chat_engine(self):
        """懒加载 ChatEngine（避免无网络/无 Key 时 import 报错）。"""
        if not hasattr(self, "_chat_engine") or self._chat_engine is None:
            try:
                from gui_llm_bridge import ChatEngine
                self._chat_engine = ChatEngine(config_path="config.json")
            except Exception:
                self._chat_engine = None
        return self._chat_engine

    def _page_chat(self, parent):
        top = tk.Frame(parent, bg="#f4f7fb")
        top.pack(fill="both", expand=True, padx=20, pady=15)

        # 顶部：标题 + 模式指示 + ⚙️ 设置
        header = tk.Frame(top, bg="#f4f7fb")
        header.pack(fill="x")
        tk.Label(header, text="💬 AI 对话练习", font=("WenQuanYi Micro Hei", 22, "bold"),
                 fg="#222", bg="#f4f7fb").pack(side="left")
        self.chat_mode_label = tk.Label(header, text="", font=("WenQuanYi Micro Hei", 10),
                                        fg="#4a6cf7", bg="#f4f7fb")
        self.chat_mode_label.pack(side="left", padx=(12, 8))
        tk.Button(header, text="⚙️ AI设置", font=("WenQuanYi Micro Hei", 10, "bold"),
                  bg="#eef2fb", fg="#4a6cf7", padx=12, pady=4, bd=0,
                  command=self._open_ai_settings).pack(side="right")
        self._refresh_chat_mode()

        self.chat_display = tk.Text(top, font=("WenQuanYi Micro Hei", 12), wrap="word",
                                    bg="white", relief="flat", padx=12, pady=12, height=18)
        self.chat_display.pack(fill="both", expand=True)
        self.chat_display.config(state="disabled")

        bottom = tk.Frame(top, bg="#f4f7fb")
        bottom.pack(fill="x", pady=(10, 0))
        self.chat_entry = tk.Entry(bottom, font=("WenQuanYi Micro Hei", 13), relief="solid", bd=1)
        self.chat_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.chat_entry.bind("<Return>", lambda e: self._send_chat())
        tk.Button(bottom, text="发送", font=("WenQuanYi Micro Hei", 12), bg="#4a6cf7", fg="white",
                  padx=20, bd=0, command=self._send_chat).pack(side="right")

        self._add_chat("AI Tutor", "Hi! I'm your AI English tutor. What do you want to talk about today? 😊")

    def _refresh_chat_mode(self):
        if not hasattr(self, "chat_mode_label"):
            return
        engine = self._get_chat_engine()
        if engine and engine.client.is_available():
            self.chat_mode_label.config(text=f"🟢 真实 LLM：{engine.client.provider}")
        else:
            self.chat_mode_label.config(text="🟡 规则模式（点击「AI设置」配置大模型 Key）")

    def _open_ai_settings(self):
        try:
            from gui_llm_bridge import build_settings_dialog
            build_settings_dialog(self, "config.json")
            # 设置保存后重建引擎，使新模式生效
            self._chat_engine = None
            self._refresh_chat_mode()
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("错误", f"无法打开设置：{e}")

    def _add_chat(self, who, text):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", f"{who}: ", "who" if who == "user" else "ai")
        self.chat_display.insert("end", text + "\n\n")
        self.chat_display.tag_config("ai", foreground="#4a6cf7", font=("WenQuanYi Micro Hei", 12, "bold"))
        self.chat_display.tag_config("who", foreground="#333", font=("WenQuanYi Micro Hei", 12, "bold"))
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def _send_chat(self):
        text = self.chat_entry.get().strip()
        if not text:
            return
        self._add_chat("You", text)
        self.chat_entry.delete(0, "end")
        engine = self._get_chat_engine()
        if engine and engine.client.is_available():
            # 真实 LLM：流式打字机效果
            self._stream_ai_reply(engine, text)
        else:
            # 无 Key：规则回复
            reply = (engine.rule.reply(text) if engine else self.ai.reply(text))
            self.after(400, lambda: self._add_chat("AI Tutor", reply))

    def _stream_ai_reply(self, engine, user_text):
        """流式回复：后台线程跑 LLM，token 经 Queue + after() 投到主线程更新 UI。"""
        import queue as _queue
        if not hasattr(self, "_chat_queue"):
            self._chat_queue = _queue.Queue()
        q = self._chat_queue
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", "AI Tutor: ", "ai")
        self.chat_display.config(state="disabled")
        engine.history.append({"role": "user", "content": user_text})

        def token_cb(delta):
            q.put(delta)

        def run():
            full = {"text": ""}
            try:
                engine.client.reply(user_text, history=engine.history[-10:],
                                    stream=True, on_token=token_cb)
            except Exception:
                # 流式失败 -> 规则兜底
                q.put(engine.rule.reply(user_text))
            q.put(None)  # 结束哨兵

        def drain():
            try:
                while True:
                    delta = q.get_nowait()
                    if delta is None:
                        self.chat_display.config(state="normal")
                        self.chat_display.insert("end", "\n\n")
                        self.chat_display.config(state="disabled")
                        self.chat_display.see("end")
                        return
                    self.chat_display.config(state="normal")
                    self.chat_display.insert("end", delta)
                    self.chat_display.config(state="disabled")
                    self.chat_display.see("end")
            except _queue.Empty:
                pass
            self.after(40, drain)

        import threading as _threading
        _threading.Thread(target=run, daemon=True).start()
        self.after(40, drain)

    # ==================== 3. 跟读练习（ASR 真实打分） ====================
    def _page_pronunciation(self, parent):
        center = tk.Frame(parent, bg="#f4f7fb")
        center.pack(expand=True, fill="both", padx=40, pady=20)

        # 顶部：标题 + ASR 模式指示 + 设置按钮
        top = tk.Frame(center, bg="#f4f7fb")
        top.pack(fill="x")
        tk.Label(top, text="🎙️ 跟读评分", font=("WenQuanYi Micro Hei", 22, "bold"),
                 fg="#222", bg="#f4f7fb").pack(side="left")
        self.pron_mode_label = tk.Label(top, text="", font=("WenQuanYi Micro Hei", 10),
                                        fg="#4a6cf7", bg="#f4f7fb")
        self.pron_mode_label.pack(side="left", padx=(12, 8))
        tk.Button(top, text="⚙️ ASR设置", font=("WenQuanYi Micro Hei", 10, "bold"),
                  bg="#eef2fb", fg="#4a6cf7", padx=12, pady=4, bd=0,
                  command=self._open_asr_settings).pack(side="right")
        self._refresh_asr_mode()

        self.pron_target = self._big_label(center, "", 30, "#4a6cf7")
        self.pron_target.pack(pady=(10, 0))
        self.pron_hint = tk.Label(center, text="点击下方按钮录音，模仿发音后停止",
                                  font=("WenQuanYi Micro Hei", 12), fg="#666", bg="#f4f7fb")
        self.pron_hint.pack(pady=5)

        self.pron_record_btn = tk.Button(center, text="⏺️ 开始录音", font=("WenQuanYi Micro Hei", 13),
                                         bg="#ff6b6b", fg="white", padx=24, pady=10, bd=0,
                                         command=self._toggle_record)
        self.pron_record_btn.pack(pady=15)

        # 评分结果（综合分 + 四维度 + 识别文本）
        self.pron_result = tk.Label(center, text="", font=("WenQuanYi Micro Hei", 15, "bold"),
                                    fg="#333", bg="#f4f7fb", justify="left")
        self.pron_result.pack(pady=(5, 2))
        self.pron_detail = tk.Label(center, text="", font=("WenQuanYi Micro Hei", 11),
                                    fg="#666", bg="#f4f7fb", justify="left", wraplength=560)
        self.pron_detail.pack(pady=(0, 5))
        self.pron_recognized = tk.Label(center, text="", font=("WenQuanYi Micro Hei", 11),
                                        fg="#888", bg="#f4f7fb", wraplength=560)
        self.pron_recognized.pack(pady=(0, 5))

        btns = tk.Frame(center, bg="#f4f7fb")
        btns.pack(pady=10)
        tk.Button(btns, text="🔄 换一句", font=("WenQuanYi Micro Hei", 11), bg="#eef2fb", fg="#4a6cf7",
                  padx=16, pady=6, bd=0, command=self._next_pron).pack(side="left", padx=6)
        tk.Button(btns, text="📖 看例句发音", font=("WenQuanYi Micro Hei", 11), bg="#fff3bf", fg="#e67700",
                  padx=16, pady=6, bd=0, command=self._speak_target).pack(side="left", padx=6)

        self.pron_sentences = [
            "Practice makes perfect.",
            "How can I improve my English?",
            "The early bird catches the worm.",
            "Where there is a will, there is a way.",
            "A journey of a thousand miles begins with a single step.",
        ]
        self._pron_idx = 0
        self._next_pron()

    def _refresh_asr_mode(self):
        if not hasattr(self, "pron_mode_label"):
            return
        if not HAS_ASR or not self.asr_config or not self.asr_config.is_real():
            self.pron_mode_label.config(text="🔇 离线模式（点击「ASR设置」配置真实识别）")
        else:
            self.pron_mode_label.config(text=f"🎧 真实 ASR：{self.asr_config.backend}")

    def _open_asr_settings(self):
        """弹出 ASR 设置：选择后端 + 填入 API Key，保存后即时生效并持久化。"""
        if not HAS_ASR:
            from tkinter import messagebox
            messagebox.showinfo("提示", "ASR 模块未加载，请确保 asr.py 与本文件在同一目录。")
            return
        win = tk.Toplevel(self)
        win.title("⚙️ ASR 语音识别设置")
        win.geometry("480x340")
        cfg = self.asr_config or asr_module.ASRConfig()

        tk.Label(win, text="选择 ASR 后端：", font=("WenQuanYi Micro Hei", 11)).pack(anchor="w", padx=16, pady=(14, 2))
        backend_var = tk.StringVar(value=cfg.backend if cfg.is_real() else "offline")
        bf = tk.Frame(win)
        bf.pack(fill="x", padx=16)
        for val, txt in [("offline", "离线（无需 Key，基于音频质量估算）"),
                         ("whisper", "OpenAI Whisper"), ("tencent", "腾讯云 ASR")]:
            tk.Radiobutton(bf, text=txt, variable=backend_var, value=val,
                           font=("WenQuanYi Micro Hei", 10)).pack(anchor="w", pady=1)

        tk.Label(win, text="API Key（离线模式可不填）：", font=("WenQuanYi Micro Hei", 11)).pack(anchor="w", padx=16, pady=(12, 2))
        key_var = tk.StringVar(value=cfg.api_key)
        tk.Entry(win, textvariable=key_var, font=("WenQuanYi Micro Hei", 11), show="*", width=40).pack(padx=16, fill="x")

        tk.Label(win, text="Endpoint / 自建服务地址（可选）：", font=("WenQuanYi Micro Hei", 11)).pack(anchor="w", padx=16, pady=(10, 2))
        endpoint_var = tk.StringVar(value=cfg.endpoint)
        tk.Entry(win, textvariable=endpoint_var, font=("WenQuanYi Micro Hei", 11), width=40).pack(padx=16, fill="x")

        status = tk.Label(win, text="", font=("WenQuanYi Micro Hei", 10), fg="#888")
        status.pack(pady=(10, 2))

        def save():
            new_cfg = asr_module.ASRConfig(
                backend=backend_var.get(), api_key=key_var.get().strip(),
                endpoint=endpoint_var.get().strip())
            self.asr_config = new_cfg
            self.scorer = PronunciationScorer(config=new_cfg)
            self._refresh_asr_mode()
            mode = "真实 ASR" if new_cfg.is_real() else "离线模式"
            status.config(text=f"✅ 已保存：{mode}（下次录音生效）", fg="#51cf66")
            # 持久化到 config.json 的 [asr] 段
            try:
                path = "config.json"
                data = {}
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                    except Exception:
                        data = {}
                data.setdefault("asr", {})
                data["asr"]["backend"] = new_cfg.backend
                if new_cfg.api_key:
                    data["asr"]["api_key"] = new_cfg.api_key
                if new_cfg.endpoint:
                    data["asr"]["endpoint"] = new_cfg.endpoint
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        tk.Button(win, text="💾 保存", font=("WenQuanYi Micro Hei", 12, "bold"),
                  bg="#4a6cf7", fg="white", padx=24, pady=6, bd=0, command=save).pack(pady=12)

    def _speak_target(self):
        """朗读当前目标句（离线用 TTS 或系统发音；失败仅提示）。"""
        target = self.pron_target.cget("text")
        if not target:
            return
        try:
            import pyttsx3  # 可选依赖
            engine = pyttsx3.init()
            engine.say(target)
            engine.runAndWait()
        except Exception:
            self.pron_hint.config(text="💡 提示：安装 pyttsx3 可启用自动朗读")

    def _next_pron(self):
        self._pron_idx = (self._pron_idx + 1) % len(self.pron_sentences)
        self.pron_target.config(text=self.pron_sentences[self._pron_idx])
        self._clear_pron_result()

    def _clear_pron_result(self):
        for w in (self.pron_result, self.pron_detail, self.pron_recognized):
            w.config(text="")

    def _toggle_record(self):
        if not HAS_AUDIO:
            # 无音频库：走"离线 ASR 打分"（模拟能量分，与真实流程同接口）
            self._score_without_audio()
            return
        if not self._recording:
            self._start_record()
        else:
            self._stop_record()

    def _start_record(self):
        try:
            self._pyaudio = pyaudio.PyAudio()
            self._stream = self._pyaudio.open(format=pyaudio.paInt16, channels=1, rate=16000,
                                              input=True, frames_per_buffer=1024)
            self._recording = True
            self._audio_frames = []
            if self.scorer:
                self.scorer.reset()
            self.pron_record_btn.config(text="⏹️ 停止并评分", bg="#888")
            self.pron_result.config(text="🔴 录音中...")
            self.pron_detail.config(text="")
            self.pron_recognized.config(text="")
            self._record_loop()
        except Exception:
            self._score_without_audio()

    def _record_loop(self):
        if not self._recording:
            return
        try:
            data = self._stream.read(1024, exception_on_overflow=False)
            self._audio_frames.append(data)
            if self.scorer:
                self.scorer.feed(data)
            self.after(30, self._record_loop)
        except Exception:
            self._stop_record()

    def _stop_record(self):
        self._recording = False
        try:
            self._stream.stop_stream()
            self._stream.close()
            self._pyaudio.terminate()
        except Exception:
            pass
        # 用 ASR 打分器评分（内部自动调后端识别；无 Key 则降级能量打分）
        self._do_score()

    def _score_without_audio(self):
        """无麦克风环境：演示 ASR 打分流程（用目标句注入为识别结果，走完整对齐逻辑）。"""
        if self.scorer:
            # 模拟"用户念得和标准基本一致" -> 走真实对齐逻辑得到合理高分
            import difflib
            result = self.scorer.score(
                self.pron_target.cget("text"),
                recognized_text=self.pron_target.cget("text").lower())
        else:
            from collections import namedtuple
            result = {"score": 88, "accuracy": 100, "completeness": 100, "fluency": 90,
                      "quality": 80, "recognized": "", "missing": [], "feedback": "演示模式", "offline": True}
        self._render_score(result)

    def _do_score(self):
        if not self.scorer:
            self._score_without_audio()
            return
        target = self.pron_target.cget("text")
        # 真实录音：让 scorer 内部调 ASR 识别；在主线程安全调用
        def run():
            try:
                result = self.scorer.score(target)
            except Exception:
                result = None
            self.after(0, lambda: self._render_score(result))
        # 避免阻塞 UI：开线程跑 ASR（网络/SDK 可能较慢）
        threading.Thread(target=run, daemon=True).start()
        self.pron_result.config(text="⏳ 识别并评分中...")

    def _render_score(self, result):
        self.pron_record_btn.config(text="⏺️ 开始录音", bg="#ff6b6b")
        if not result:
            self.pron_result.config(text="评分失败，请重试", fg="#ff6b6b")
            return
        comment, color = PronunciationScorer.comment(result["score"]) if HAS_ASR else ("", "#333")
        self.pron_result.config(
            text=f"综合得分：{result['score']} 分 — {comment}", fg=color)
        self.pron_detail.config(
            text=f"文本准确率 {result.get('accuracy', 0)}  ·  完整度 {result.get('completeness', 0)}  "
                 f"·  流畅度 {result.get('fluency', 0)}  ·  音频质量 {result.get('quality', 0)}")
        rec = result.get("recognized", "")
        if rec:
            self.pron_recognized.config(text=f"识别结果：{rec}")
        elif result.get("offline"):
            self.pron_recognized.config(text="（离线模式：未配置 ASR，分数基于音频质量估算）")
        # 记录到学习统计（连续打卡）
        self.store.update_streak()

    # ==================== 4. 智能测验 ====================
    def _page_quiz(self, parent):
        center = tk.Frame(parent, bg="#f4f7fb")
        center.pack(expand=True, fill="both", padx=40, pady=20)

        self.quiz_score_label = tk.Label(center, text="", font=("WenQuanYi Micro Hei", 12),
                                         fg="#888", bg="#f4f7fb")
        self.quiz_score_label.pack(anchor="e")

        self.quiz_q = self._big_label(center, "", 22, "#222")
        self.quiz_q.pack(pady=(10, 15))

        self.quiz_options = tk.Frame(center, bg="#f4f7fb")
        self.quiz_options.pack(fill="x")

        self.quiz_feedback = tk.Label(center, text="", font=("WenQuanYi Micro Hei", 13),
                                      fg="#333", bg="#f4f7fb")
        self.quiz_feedback.pack(pady=15)

        tk.Button(center, text="🔄 开始新测验", font=("WenQuanYi Micro Hei", 12), bg="#4a6cf7", fg="white",
                  padx=20, pady=8, bd=0, command=self._start_quiz).pack()

        self.quiz_data = []
        self.quiz_pos = 0
        self.quiz_correct = 0
        self._start_quiz()

    def _start_quiz(self):
        # 生成 10 道选择题（含自定义词库）
        words = self.store.wordbook.all_words()[:]
        random.shuffle(words)
        self.quiz_data = []
        pool_meanings = [x["meaning"] for x in self.store.wordbook.all_words()]
        for w in words[:10]:
            others = [m for m in pool_meanings if m != w["meaning"]]
            if len(others) < 3:
                others = pool_meanings  # 词库太小时允许重复干扰项
            choices = random.sample(others, min(3, len(others))) + [w["meaning"]]
            random.shuffle(choices)
            self.quiz_data.append({"q": f"「{w['word']}」 的意思是？", "answer": w["meaning"], "choices": choices})
        self.quiz_pos = 0
        self.quiz_correct = 0
        self._render_quiz()

    def _render_quiz(self):
        for widget in self.quiz_options.winfo_children():
            widget.destroy()
        self.quiz_feedback.config(text="")
        if self.quiz_pos >= len(self.quiz_data):
            total = len(self.quiz_data)
            self.quiz_q.config(text=f"测验完成！得分 {self.quiz_correct}/{total}")
            self.quiz_score_label.config(text="")
            # 记录历史
            self.store.data["quiz_history"].append({
                "date": datetime.date.today().isoformat(),
                "score": self.quiz_correct, "total": total
            })
            self.store.save()
            return
        item = self.quiz_data[self.quiz_pos]
        self.quiz_q.config(text=f"Q{self.quiz_pos+1}. {item['q']}")
        self.quiz_score_label.config(text=f"进度 {self.quiz_pos+1}/{len(self.quiz_data)}")
        for choice in item["choices"]:
            tk.Button(self.quiz_options, text=choice, font=("WenQuanYi Micro Hei", 12),
                      bg="white", fg="#333", anchor="w", padx=12, pady=6, relief="solid", bd=1,
                      command=lambda c=choice: self._answer_quiz(c)).pack(fill="x", pady=3)

    def _answer_quiz(self, choice):
        item = self.quiz_data[self.quiz_pos]
        if choice == item["answer"]:
            self.quiz_correct += 1
            self.quiz_feedback.config(text="✅ 正确！", fg="#51cf66")
        else:
            self.quiz_feedback.config(text=f"❌ 正确答案：{item['answer']}", fg="#ff6b6b")
        self.quiz_pos += 1
        self.after(900, self._render_quiz)

    # ==================== 5. 学习统计 ====================
    def _page_stats(self, parent):
        center = tk.Frame(parent, bg="#f4f7fb")
        center.pack(expand=True, fill="both", padx=40, pady=20)

        tk.Label(center, text="📊 学习统计", font=("WenQuanYi Micro Hei", 22, "bold"),
                 fg="#222", bg="#f4f7fb").pack(pady=(0, 15))

        self.stats_cards = tk.Frame(center, bg="#f4f7fb")
        self.stats_cards.pack(fill="x")

        # 用 grid 排布统计卡片
        self.stat_widgets = {}
        info = [
            ("streak", "🔥 连续打卡", "0 天"),
            ("words", "📚 已掌握单词", "0"),
            ("quiz", "🏆 最佳测验", "0/0"),
            ("history", "📈 测验次数", "0"),
        ]
        for i, (key, title, val) in enumerate(info):
            card = tk.Frame(self.stats_cards, bg="white", highlightbackground="#dbe4fb", highlightthickness=1)
            card.grid(row=0, column=i, padx=8, sticky="nsew")
            self.stats_cards.columnconfigure(i, weight=1)
            tk.Label(card, text=title, font=("WenQuanYi Micro Hei", 11), fg="#888", bg="white").pack(pady=(12, 2))
            lbl = tk.Label(card, text=val, font=("WenQuanYi Micro Hei", 20, "bold"), fg="#4a6cf7", bg="white")
            lbl.pack(pady=(0, 12))
            self.stat_widgets[key] = lbl

        # 历史记录
        tk.Label(center, text="近期测验记录", font=("WenQuanYi Micro Hei", 14, "bold"),
                 fg="#333", bg="#f4f7fb").pack(anchor="w", pady=(20, 5))
        self.history_text = tk.Text(center, font=("WenQuanYi Micro Hei", 11), height=8,
                                    bg="white", relief="flat", wrap="word")
        self.history_text.pack(fill="both", expand=True)

    def _refresh_stats(self):
        if not hasattr(self, "stat_widgets"):
            return
        words = self.store.data["words"]
        mastered = sum(1 for v in words.values() if v.get("level", 0) >= 3)
        history = self.store.data.get("quiz_history", [])
        best = max((f"{h['score']}/{h['total']}" for h in history), default="0/0")

        self.stat_widgets["streak"].config(text=f"{self.store.data.get('streak', 0)} 天")
        self.stat_widgets["words"].config(text=str(mastered))
        self.stat_widgets["quiz"].config(text=best)
        self.stat_widgets["history"].config(text=str(len(history)))

        self.history_text.config(state="normal")
        self.history_text.delete("1.0", "end")
        if not history:
            self.history_text.insert("end", "暂无记录，去做几道测验吧！")
        else:
            for h in reversed(history[-15:]):
                self.history_text.insert("end", f"  {h['date']}    得分 {h['score']}/{h['total']}\n")
        self.history_text.config(state="disabled")

        self.streak_label.config(text=f"🔥 连续 {self.store.data.get('streak', 0)} 天")


def main():
    app = EnglishApp()
    app.mainloop()


if __name__ == "__main__":
    main()
