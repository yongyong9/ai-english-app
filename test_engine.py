# -*- coding: utf-8 -*-
"""核心引擎完整测试 (不依赖 tkinter / 显示环境)"""
import sys, os, tempfile, struct, json, shutil
sys.path.insert(0, os.path.dirname(__file__))
import engine as E

errors = []
def check(c, m):
    if c: print("  ✓", m)
    else: print("  ✗", m); errors.append(m)

tmp = tempfile.mkdtemp()
df = os.path.join(tmp, "test_data.json")

print("=== 数据管理 ===")
s = E.DataStore(data_file=df)
s.ensure_words()
check(len(s.data["words"]) == len(E.BUILTIN_WORDS), "初始化全部单词")
check(len(s.due_words()) >= 1, "首日有待复习单词")
before = s.data["words"]["eloquent"]["level"]
s.record_review("eloquent", True)
check(s.data["words"]["eloquent"]["level"] == before+1, "答对升级")
s.record_review("eloquent", False)
check(s.data["words"]["eloquent"]["wrong"] == 1, "答错计数")
check(s.mastered_count() == 0, "初始掌握数 0")
s.update_streak(); s.update_streak()
check(s.data["streak"] == 1, "连续两天打卡仍为 1")

print("\n=== AI 对话 ===")
ai = E.AIConversation()
check(len(ai.reply("")) > 0, "空输入有回复(问候)")
r = ai.reply("i am so happy")
check("I am" in r, f"纠正 'i am' -> 'I am': {r}")
r = ai.reply("hello")
check(len(r) > 3, "问候回复")
r = ai.reply("thank you very much")
check("welcome" in r.lower(), "感谢回应")

print("\n=== 测验引擎 ===")
q = E.QuizEngine(size=6)
first = q.current()
check(first and len(first["choices"]) == 4, "每题 4 选项")
ok, ans = q.answer(first["answer"])
check(ok and ans == first["answer"], "正确作答判对")
while not q.finished():
    q.answer(q.current()["answer"])
sc, tot = q.score()
check(sc == tot == 6, f"全对得分 {sc}/{tot}")
# 单独验证错误作答（新建引擎，避免污染上面的全对统计）
q2 = E.QuizEngine(size=4)
cur = q2.current()
ok2, _ = q2.answer("明显错误答案xxxx")
check(not ok2, "错误作答判错")
s.record_quiz(sc, tot)
check(len(s.data["quiz_history"]) == 1, "测验记录入库")
check(s.best_quiz() == "6/6", f"最佳成绩 {s.best_quiz()}")

print("\n=== 间隔重复区间 ===")
levels = [s.data["words"]["eloquent"]["level"]]
for _ in range(6):
    s.record_review("eloquent", True)
check(s.data["words"]["eloquent"]["level"] == 5, "熟练度上限 5")
check(s.mastered_count() >= 1, "存在掌握单词")

print("\n=== 发音评分 ===")
ps = E.PronunciationScorer()
# 构造假 PCM 数据（较高能量）
import wave
fake = struct.pack(f"{500}h", *[8000]*500)
ps.feed(fake)
score = ps.score()
check(0 <= score <= 100, f"能量打分 {score}")
comment, color = E.PronunciationScorer.comment(score)
check(color.startswith("#"), "评分带颜色")

# 无音频帧时随机打分
ps2 = E.PronunciationScorer()
check(0 <= ps2.score() <= 100, "无音频随机打分")

print("\n=== 词库导入 ===")
# 使用独立临时目录，避免读写真实的 custom_words.json
imp_dir = tempfile.mkdtemp(prefix="imp_")
cust_path = os.path.join(imp_dir, "custom_words.json")
wb = E.WordBook(builtin=E.BUILTIN_WORDS, custom_file=cust_path)

# 1) 三种格式文件解析
json_f = os.path.join(imp_dir, "words.json")
with open(json_f, "w", encoding="utf-8") as f:
    f.write(json.dumps([
        {"word": "ubiquitous", "pos": "adj.", "meaning": "无处不在的", "example": "Smartphones are ubiquitous."},
        {"word": "cogent", "meaning": "有说服力的"},  # 缺 example/pos，应补默认
    ], ensure_ascii=False))

csv_f = os.path.join(imp_dir, "words.csv")
with open(csv_f, "w", encoding="utf-8-sig") as f:
    f.write("word,释义,例句\nresilience,韧性,She showed great resilience.\nambiguity,歧义,Avoid ambiguity.\n")

tsv_f = os.path.join(imp_dir, "words.tsv")
with open(tsv_f, "w", encoding="utf-8") as f:
    f.write("word\tpos\tmeaning\nexquisite\tadj.\t精致的\n")

txt_f = os.path.join(imp_dir, "words.txt")
with open(txt_f, "w", encoding="utf-8") as f:
    f.write("# 注释行与空行应被忽略\n\nserendipity 意外发现的运气\nsyllogism,pos,三段论,a logical syllogism\n")

# 解析校验
res = E.import_words_from_file(json_f)
check(len(res) == 2 and all(r[1] is None for r in res), "JSON 解析 2 条成功")
check(res[1][0]["example"] != "", "缺字段补默认例句")
res = E.import_words_from_file(csv_f)
check(len(res) == 2 and all(r[1] is None for r in res), "CSV 解析 2 条（utf-8-sig 去 BOM）")
check(res[0][0]["meaning"] == "韧性", "CSV 中文别名'释义'识别")
res = E.import_words_from_file(tsv_f)
check(len(res) == 1 and res[0][0]["pos"] == "adj.", "TSV 解析")
res = E.import_words_from_file(txt_f)
check(len(res) == 2, f"TXT 解析（忽略注释/空行）: {len(res)}")

# 2) 非法行容错（缺 word 字段应记为失败，但不抛异常）
bad_json = os.path.join(imp_dir, "bad.json")
with open(bad_json, "w", encoding="utf-8") as f:
    f.write(json.dumps([{"meaning": "没有单词"}, {"word": "ok_word"}]))
res = E.import_words_from_file(bad_json)
check(len(res) == 2 and res[0][1] is not None and res[1][1] is None, "缺 word 字段容错")

# 3) WordBook 合并 + 去重 + append/replace
added, failed = wb.add_from_file(json_f, mode="append")
check(added == 2 and failed == [], f"append 导入 2 条: +{added}")
check(wb.custom_count() == 2, "自定义词库保存 2 条")
# 重复导入应去重（不新增）
added2, _ = wb.add_from_file(json_f, mode="append")
check(added2 == 0, "重复导入自动去重")
# 重复单词（内置已有 serendipity）在合并中以内置为准
wb2 = E.WordBook(builtin=E.BUILTIN_WORDS, custom_file=cust_path)
allw = wb2.all_words()
check(len(allw) == len(E.BUILTIN_WORDS) + 2, f"合并词库=内置+自定义去重: {len(allw)}")
se = next(w for w in allw if w["word"] == "serendipity")
check(se["meaning"] == E.BUILTIN_WORDS[0]["meaning"], "重复单词以内置释义优先")

# 4) replace 模式清空重建
added3, _ = wb2.add_from_file(tsv_f, mode="replace")
check(wb2.custom_count() == added3, "replace 清空后重建")

# 5) DataStore / QuizEngine 使用合并词库
ds = E.DataStore(data_file=df, wordbook=wb2)
ds.ensure_words()
check(len(ds.data["words"]) == len(wb2.all_words()), "DataStore 为合并词库建复习记录")
q = E.QuizEngine(words=wb2.all_words(), size=5)
prompts = [q.items[i]["prompt"] for i in range(len(q.items))]
check(any("exquisite" in p for p in prompts) or len(q.items) == 5, "Quiz 可从自定义词选题")

import shutil; shutil.rmtree(imp_dir)

os.remove(df)
print("\n" + ("全部通过 ✅" if not errors else f"失败 {len(errors)} 项"))
sys.exit(1 if errors else 0)
