# -*- coding: utf-8 -*-
"""
端到端冒烟测试（无需 tkinter / 麦克风 / 网络）
模拟真实用户完整流程，验证 ①②③⑤ 全部功能协同无回归：
  1. 词库初始化 + 自定义导入  2. 间隔重复  3. 智能测验
  4. ASR 跟读打分（完美/部分/离线/无帧）  5. LLM 降级对话
  6. config.json 配置持久化（LLM + ASR）
"""
import os
import sys
import json
import struct
import tempfile
import subprocess
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine
import asr
import llm
import gui_llm_bridge


class E2ESmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp()
        cls._orig = os.getcwd()
        os.chdir(cls._tmp)

    @classmethod
    def tearDownClass(cls):
        os.chdir(cls._orig)
        for f in os.listdir(cls._tmp):
            os.remove(os.path.join(cls._tmp, f))
        os.rmdir(cls._tmp)

    def test_1_wordbook_and_spaced_repetition(self):
        wb = engine.WordBook()
        self.assertEqual(len(wb.all_words()), 15)
        # 用 JSON 临时文件导入自定义词
        path = os.path.join(self._tmp, "imp.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump([{"word": "ubiquitous", "meaning": "无处不在的"}], f)
        added, failed = wb.add_from_file(path)
        self.assertEqual(added, 1)
        self.assertEqual(len(wb.all_words()), 16)
        # 间隔重复
        store = engine.DataStore(wordbook=wb)
        store.ensure_words()
        store.record_review("ubiquitous", correct=True)
        self.assertEqual(store.data["words"]["ubiquitous"]["level"], 1)

    def test_2_quiz_from_merged_book(self):
        wb = engine.WordBook()
        qe = engine.QuizEngine(words=wb.all_words(), size=5)
        self.assertEqual(len(qe.items), 5)
        ok, ans = qe.answer(qe.items[0]["answer"])
        self.assertTrue(ok)

    def test_3_asr_perfect(self):
        scorer = asr.PronunciationScorer(asr.ASRConfig(backend="offline"))
        r = scorer.score("practice makes perfect", recognized_text="practice makes perfect")
        self.assertGreaterEqual(r["score"], 85)
        self.assertEqual(r["missing"], [])

    def test_4_asr_partial_and_offline(self):
        scorer = asr.PronunciationScorer(asr.ASRConfig(backend="offline"))
        r = scorer.score("practice makes perfect today", recognized_text="practice perfect")
        self.assertLess(r["completeness"], 100)
        self.assertIn("makes", r["missing"])
        # 离线降级：无帧无识别
        scorer.reset()
        r2 = scorer.score("hello", recognized_text="")
        self.assertGreaterEqual(r2["score"], 30)

    def test_5_llm_degrade_to_rule(self):
        # 无 Key -> 降级规则回复
        client = llm.LLMClient({})
        self.assertFalse(client.is_available())
        eng = gui_llm_bridge.ChatEngine(config_path="config.json")
        reply = eng.reply("hello")
        self.assertIn("Hello", reply)  # 规则命中 greeting
        # 流式：无 Key 走 fake_stream，on_token 累积文本
        collected = []
        eng.stream_reply("hi", on_token=collected.append)
        self.assertTrue(any("Hello" in c for c in collected) or collected)

    def test_6_config_persistence(self):
        data = {
            "llm": {"provider": "deepseek", "api_key": "ds-key", "model": "deepseek-chat"},
            "asr": {"backend": "whisper", "api_key": "ws-key"},
        }
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(data, f)
        # LLM 配置
        llm_cfg = llm.load_llm_config("config.json")
        self.assertEqual(llm_cfg["provider"], "deepseek")
        c = llm.LLMClient(llm_cfg)
        self.assertTrue(c.is_available())
        self.assertEqual(c.model, "deepseek-chat")
        # ASR 配置
        a = asr.ASRConfig(config_path="config.json")
        self.assertEqual(a.backend, "whisper")
        self.assertTrue(a.is_real())  # 有 api_key 时为真实后端
        self.assertIsInstance(asr.make_backend(a), asr.WhisperBackend)


if __name__ == "__main__":
    unittest.main(verbosity=2)
