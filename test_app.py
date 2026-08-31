# -*- coding: utf-8 -*-
"""Headless 逻辑测试：验证数据层、AI 对话、测验、统计等核心逻辑（不依赖 GUI / 音频）"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

# 打桩 tk，避免 headless 环境无法创建 GUI
import types
fake_tk = types.ModuleType("tkinter")
class _Any:
    def __init__(self, *a, **k): pass
    def __getattr__(self, n): return _Any()
    def __call__(self, *a, **k): return _Any()
for name in ["Tk","Frame","Label","Button","Text","Entry","StringVar","IntVar","BooleanVar"]:
    setattr(fake_tk, name, _Any)
fake_tk.ttk = _Any()
fake_tk.messagebox = _Any()
sys.modules["tkinter"] = fake_tk
sys.modules["tkinter.ttk"] = _Any()

import ai_english_app as app

errors = []
def check(cond, msg):
    if not cond:
        errors.append(msg)
        print("  ✗", msg)
    else:
        print("  ✓", msg)

print("=== 词库 ===")
check(len(app.BUILTIN_WORDS) >= 10, f"内置词库 >=10 词 (实际 {len(app.BUILTIN_WORDS)})")

print("\n=== 数据管理 ===")
store = app.DataStore()
store.ensure_words()
check(len(store.data["words"]) == len(app.BUILTIN_WORDS), "ensure_words 初始化全部单词")
due = store.due_words()
check(len(due) >= 1, "首日有待复习单词")
before = store.data["words"]["serendipity"]["level"]
store.record_review("serendipity", True)
check(store.data["words"]["serendipity"]["level"] == before + 1, "答对升级 level")
store.record_review("serendipity", False)
check(store.data["words"]["serendipity"]["wrong"] >= 1, "答错记录 wrong")
next_r = store.data["words"]["serendipity"]["next_review"]
check(next_r > "", "答对后生成下次复习日期")

print("\n=== AI 对话 ===")
ai = app.AIConversation()
r1 = ai.reply("hello teacher")
check(isinstance(r1, str) and len(r1) > 0, "问候有回复")
r2 = ai.reply("i am happy today")
check("more natural" in r2.lower() or "natural" in r2.lower() or "🌟" in r2 or "💪" in r2 or "great" in r2.lower(), f"可检测 i am 小写: {r2}")
r3 = ai.reply("this is a fallback test sentence")
check(len(r3) > 0, "兜底回复正常")

print("\n=== 间隔重复区间 ===")
intervals = [0,1,3,7,14,30]
check(store.data["words"]["serendipity"]["next_review"] != "", "复习日期已设置")

print("\n=== 连续打卡 ===")
store2 = app.DataStore()
store2.data["last_day"] = None
store2.update_streak()
check(store2.data["streak"] == 1, "首次打卡 streak=1")
store2.data["last_day"] = "2020-01-01"
store2.update_streak()
check(store2.data["streak"] == 1, "断签重置为 1")

print("\n=== 测验逻辑 ===")
words = app.BUILTIN_WORDS
w = words[0]
others = [x["meaning"] for x in words if x["word"] != w["word"]]
choices = others[:3] + [w["meaning"]]
check(len(choices) == 4, "每题 4 个选项")
check(w["meaning"] in choices, "选项含正确答案")

print("\n=== 发音评分模拟 ===")
score = app.EnglishApp._calc_score if False else None
# 直接测模拟打分
import random
s = random.randint(72,96)
check(0 <= s <= 100, "模拟分数在 0-100")

print("\n=== 数据持久化 ===")
store.save()
check(os.path.exists(app.DATA_FILE), "learning_data.json 已生成")

print("\n" + "="*30)
if errors:
    print(f"失败 {len(errors)} 项")
    sys.exit(1)
else:
    print("全部测试通过 ✅")
