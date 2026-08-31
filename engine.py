# -*- coding: utf-8 -*-
"""
AI 学英语 - 核心引擎 (engine.py)
独立于 tkinter 的业务逻辑：词库、数据持久化、间隔重复、AI 对话、测验、发音评分。
GUI (ai_english_app.py) 通过调用本模块与数据交互。
这样即使在没有 tkinter / 显示环境也能完整测试核心功能。
"""
import os
import json
import random
import datetime

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "learning_data.json")
# 用户自定义词库（追加到此文件，与内置词库合并使用）
CUSTOM_WORDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_words.json")
# 支持的导入文件后缀
SUPPORTED_IMPORT_EXTS = (".csv", ".tsv", ".json", ".txt")

# 导入文件的字段名（中文 / 英文皆可，大小写不敏感）
FIELD_MAP = {
    "word": ["word", "单词", "vocabulary", "term"],
    "pos": ["pos", "词性", "part_of_speech", "part"],
    "meaning": ["meaning", "释义", "中文", "definition", "trans"],
    "example": ["example", "例句", "sentence", "sent"],
}

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

def _pick_field(row, field_key):
    """从一行字典中，按 FIELD_MAP 里任意别名取值，找不到返回空串。"""
    candidates = FIELD_MAP.get(field_key, [field_key])
    # 先精确匹配别名（大小写不敏感）
    lowered = {k.lower(): v for k, v in row.items()}
    for alias in candidates:
        if alias.lower() in lowered:
            return (lowered[alias.lower()] or "").strip()
    # 兜底：按子串模糊匹配（如 "英文单词" 也能命中 "word"）
    for key in lowered:
        for alias in candidates:
            if alias.lower() in key:
                return (lowered[key] or "").strip()
    return ""


def _normalize_word(row):
    """把一行原始 dict 规范成标准词项；缺字段补默认值；非法则返回 None。"""
    word = _pick_field(row, "word").strip()
    if not word:
        return None
    return {
        "word": word,
        "pos": _pick_field(row, "pos") or "",
        "meaning": _pick_field(row, "meaning") or "（暂无释义，可在编辑器中补充）",
        "example": _pick_field(row, "example") or f"Please look up the usage of \"{word}\".",
    }


def import_words_from_file(path):
    """
    从文件导入词项，返回 [(word_dict, error_msg_or_None), ...]。
    支持格式：
      - .json ：列表 [{word, pos, meaning, example}, ...]
      - .csv/.tsv ：表头 + 行，字段名可为中英文别名
      - .txt  ：一行一个，支持
            word 释义
            word,pos,meaning,example
            word\tmeaning
    """
    path = os.path.abspath(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在：{path}")
    ext = os.path.splitext(path)[1].lower()
    rows = []

    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("JSON 文件应为对象数组，如 [{\"word\": \"...\", \"meaning\": \"...\"}]")
        rows = [dict(r) for r in data]

    elif ext in (".csv", ".tsv"):
        import csv
        delim = "\t" if ext == ".tsv" else ","
        with open(path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=delim)
            rows = [dict(r) for r in reader]

    elif ext == ".txt":
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # 尝试 逗号 / 制表符 分隔（word,pos,meaning,example）
                if "," in line or "\t" in line:
                    parts = line.replace("\t", ",").split(",")
                    keys = ["word", "pos", "meaning", "example"]
                    rows.append({keys[i]: parts[i].strip() for i in range(len(parts))})
                else:
                    # 空格分隔：前半英文单词，其余当释义
                    tokens = line.split(None, 1)
                    rows.append({"word": tokens[0], "meaning": tokens[1] if len(tokens) > 1 else ""})
    else:
        raise ValueError(f"不支持的文件格式：{ext}（仅支持 {', '.join(SUPPORTED_IMPORT_EXTS)}）")

    results = []
    for r in rows:
        norm = _normalize_word(r)
        results.append((norm, None) if norm else (r, "缺少必填字段 word"))
    return results


class WordBook:
    """
    合并词库：内置词库 + 用户自定义词库。
    自定义词库持久化在 custom_words.json，可随时追加 / 覆盖重建。
    """

    def __init__(self, builtin=None, custom_file=CUSTOM_WORDS_FILE):
        self.custom_file = custom_file
        self.builtin = builtin if builtin is not None else BUILTIN_WORDS
        self.custom = self._load_custom()

    # -------- 自定义词持久化 --------
    def _load_custom(self):
        if os.path.exists(self.custom_file):
            try:
                with open(self.custom_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return [self._clean(c) for c in data if c.get("word")]
            except Exception:
                pass
        return []

    def _save_custom(self):
        with open(self.custom_file, "w", encoding="utf-8") as f:
            json.dump(self.custom, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _clean(item):
        return {
            "word": (item.get("word") or "").strip(),
            "pos": (item.get("pos") or "").strip(),
            "meaning": (item.get("meaning") or "").strip(),
            "example": (item.get("example") or "").strip(),
        }

    # -------- 对外接口 --------
    def all_words(self):
        """合并后词库（内置优先，自定义中重复单词会被内置覆盖）。"""
        by_word = {w["word"].lower(): w for w in self.builtin}
        for w in self.custom:
            key = w["word"].lower()
            if key not in by_word:
                by_word[key] = w
        return list(by_word.values())

    def add_custom(self, word_dict):
        """追加单个词项（去重），返回是否新增。"""
        norm = _normalize_word(word_dict)
        if not norm:
            return False
        key = norm["word"].lower()
        for i, w in enumerate(self.custom):
            if w["word"].lower() == key:
                self.custom[i] = norm  # 同名覆盖
                self._save_custom()
                return False
        self.custom.append(norm)
        self._save_custom()
        return True

    def add_from_file(self, path, mode="append"):
        """
        从文件批量导入。
        mode: "append"（追加去重，默认）或 "replace"（先清空自定义词库再导入）。
        返回 (成功导入条数, 失败列表)。
        """
        if mode == "replace":
            self.custom = []
        results = import_words_from_file(path)
        added, failed = 0, []
        seen = {w["word"].lower() for w in self.custom}
        for norm, err in results:
            if err or not norm:
                failed.append((norm.get("word", "") if norm else "", err or "解析失败"))
                continue
            key = norm["word"].lower()
            if key in seen:
                continue
            seen.add(key)
            self.custom.append(norm)
            added += 1
        self._save_custom()
        return added, failed

    def remove_custom(self, word):
        key = (word or "").strip().lower()
        before = len(self.custom)
        self.custom = [w for w in self.custom if w["word"].lower() != key]
        if len(self.custom) != before:
            self._save_custom()
            return True
        return False

    def custom_count(self):
        return len(self.custom)


# 每天对应的复习间隔（天数），随熟练度(level)递增
INTERVALS = [0, 1, 3, 7, 14, 30]


class DataStore:
    def __init__(self, data_file=DATA_FILE, wordbook=None):
        self.data_file = data_file
        self.wordbook = wordbook or WordBook()
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default()

    def _default(self):
        return {
            "words": {},
            "quiz_history": [],
            "streak": 0,
            "last_day": None,
            "chat_log": [],
        }

    def save(self):
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def ensure_words(self):
        today = datetime.date.today().isoformat()
        for w in self.wordbook.all_words():
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
        interval = INTERVALS[w["level"]]
        next_date = datetime.date.today() + datetime.timedelta(days=interval)
        w["next_review"] = next_date.isoformat()
        self.save()

    def due_words(self):
        today = datetime.date.today().isoformat()
        return [w for w in self.wordbook.all_words()
                if self.data["words"].get(w["word"], {}).get("next_review", today) <= today]

    def mastered_count(self):
        return sum(1 for v in self.data["words"].values() if v.get("level", 0) >= 3)

    def update_streak(self):
        today = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        if self.data["last_day"] == today:
            return
        if self.data["last_day"] == yesterday:
            self.data["streak"] += 1
        else:
            self.data["streak"] = 1
        self.data["last_day"] = today
        self.save()

    def record_quiz(self, score, total):
        self.data["quiz_history"].append({
            "date": datetime.date.today().isoformat(),
            "score": score, "total": total
        })
        self.save()

    def best_quiz(self):
        history = self.data.get("quiz_history", [])
        if not history:
            return "0/0"
        best = max(history, key=lambda h: h["score"])
        return f"{best['score']}/{best['total']}"


class AIConversation:
    """规则 + 模板模拟 AI 外教。真实部署可替换为 OpenAI / 腾讯混元等 API。"""
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
        }
        # (关键词列表, 建议替换, 提示) — 任一关键词命中即给改进建议
        self.corrections = [
            (["i am", "i'm"], "I am", "remember to capitalize 'I' in English."),
            (["dont", "don't"], "don't", "use the apostrophe correctly."),
            (["very good", "very nice"], None, "try a stronger adjective like 'fantastic' or 'wonderful'."),
            (["maybe"], None, "try 'perhaps' or 'possibly' to sound more formal."),
        ]

    def reply(self, user_text):
        text = (user_text or "").strip().lower()
        if not text:
            return random.choice(self.templates["greeting"])
        for keywords, suggestion, tip in self.corrections:
            for kw in keywords:
                if kw in text:
                    if suggestion:
                        return f"Good try! A more natural way: \"{suggestion}\". ({tip})"
                    return f"Nice! Tip: {tip}"
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
        return "That's a great point! Tell me more."


class QuizEngine:
    """生成选择题测验并判分。words 缺省时使用内置 + 自定义合并词库。"""
    def __init__(self, words=None, size=10):
        if words is None:
            words = WordBook().all_words()
        self.words = words
        self.items = []
        self.pos = 0
        self.correct = 0
        self._build(size)

    def _build(self, size):
        pool = self.words[:]
        random.shuffle(pool)
        self.items = []
        for w in pool[:size]:
            others = [x["meaning"] for x in self.words if x["word"] != w["word"]]
            choices = random.sample(others, 3) + [w["meaning"]]
            random.shuffle(choices)
            self.items.append({
                "prompt": f"「{w['word']}」 的意思是？",
                "answer": w["meaning"],
                "choices": choices,
            })
        self.pos = 0
        self.correct = 0

    def current(self):
        if self.finished():
            return None
        return self.items[self.pos]

    def finished(self):
        return self.pos >= len(self.items)

    def answer(self, choice):
        """作答，返回 (是否正确, 正确答案)。"""
        item = self.items[self.pos]
        ok = choice == item["answer"]
        if ok:
            self.correct += 1
        self.pos += 1
        return ok, item["answer"]

    def score(self):
        return self.correct, len(self.items)


class PronunciationScorer:
    """发音评分器：真实产品接 ASR；此处基于音频能量模拟，无音频时随机打分。"""
    def __init__(self):
        self.frames = []  # 16-bit PCM 帧

    def feed(self, pcm_frame):
        self.frames.append(pcm_frame)

    def reset(self):
        self.frames = []

    def score(self):
        if not self.frames:
            return random.randint(72, 96)
        import struct
        energies = []
        for frame in self.frames:
            try:
                samples = struct.unpack(f"{len(frame)//2}h", frame)
                energies.extend(abs(s) for s in samples)
            except Exception:
                pass
        avg = sum(energies) / max(len(energies), 1)
        s = min(98, int(50 + avg / 200))
        return max(s, random.randint(55, 70))

    @staticmethod
    def comment(score):
        if score >= 85:
            return "优秀！发音很标准 🌟", "#51cf66"
        if score >= 70:
            return "不错，再注意一下语调 👍", "#fab005"
        return "需要多练习哦，注意发音清晰度 💪", "#ff6b6b"


# 便捷构造
def create_store():
    store = DataStore()
    store.ensure_words()
    return store
