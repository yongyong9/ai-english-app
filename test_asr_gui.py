# -*- coding: utf-8 -*-
"""
集成测试：GUI 跟读练习页 与 ASR 打分链路
mock tkinter，无显示环境可跑；无 tkinter 时优雅跳过。
"""
import os
import sys
import json
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HAS_TK = False
try:
    import tkinter as tk  # noqa
    HAS_TK = True
except ImportError:
    pass

if HAS_TK:
    tk.Tk = MagicMock
    tk.Frame = MagicMock
    tk.Label = MagicMock
    tk.Button = MagicMock
    tk.Toplevel = MagicMock
    tk.Entry = MagicMock
    tk.Radiobutton = MagicMock
    tk.StringVar = MagicMock
    tk.Text = MagicMock
    sys.modules["tkinter"].messagebox = MagicMock()
    import ai_english_app as app


@unittest.skipUnless(HAS_TK, "tkinter 未安装，跳过 GUI 集成测试（核心 ASR 逻辑由 test_asr.py 覆盖）")
class TestPronunciationASRIntegration(unittest.TestCase):
    def setUp(self):
        self.app = app.EnglishApp()

        class FakeLabel:
            """记录最后一次 config(text=...)，便于断言渲染输出。"""
            def __init__(self, *a, **kw):
                self._text = kw.get("text", "")
                self._fg = ""
            def config(self, **kw):
                if "text" in kw:
                    self._text = kw["text"]
                if "fg" in kw:
                    self._fg = kw["fg"]
            def cget(self, key):
                return self._text if key == "text" else ""

        for name in ("pron_result", "pron_detail", "pron_recognized",
                     "pron_record_btn", "pron_mode_label"):
            setattr(self.app, name, FakeLabel())
        self.app.pron_target = FakeLabel(text="Practice makes perfect.")
        if not self.app.scorer:
            self.app.scorer = app.PronunciationScorer(config=app.asr_module.ASRConfig())

    def test_scorer_initialized(self):
        self.assertIsNotNone(self.app.scorer)
        self.assertIsNotNone(self.app.asr_config)

    def test_refresh_asr_mode_offline(self):
        self.app.asr_config = app.asr_module.ASRConfig(backend="offline", api_key="")
        self.app._refresh_asr_mode()
        self.assertIn("离线", self.app.pron_mode_label._text)

    def test_refresh_asr_mode_real(self):
        self.app.asr_config = app.asr_module.ASRConfig(backend="whisper", api_key="sk-test")
        self.app._refresh_asr_mode()
        self.assertIn("whisper", self.app.pron_mode_label._text)

    def test_score_without_audio_uses_alignment(self):
        # 无麦克风：以目标句作识别文本，走完整对齐逻辑
        self.app._score_without_audio()
        self.assertIn("得分", self.app.pron_result._text)
        self.assertIn("准确", self.app.pron_detail._text)

    def test_render_score_displays_all_fields(self):
        result = {
            "score": 92, "accuracy": 100, "completeness": 100,
            "fluency": 90, "quality": 85, "recognized": "practice makes perfect",
            "missing": [], "feedback": "good", "offline": False,
        }
        self.app._render_score(result)
        self.assertIn("92", self.app.pron_result._text)
        self.assertIn("100", self.app.pron_detail._text)
        self.assertIn("practice makes perfect", self.app.pron_recognized._text)

    def test_render_score_offline_shows_hint(self):
        result = {"score": 75, "accuracy": 0, "completeness": 0, "fluency": 60,
                  "quality": 70, "recognized": "", "missing": [], "feedback": "", "offline": True}
        self.app._render_score(result)
        self.assertIn("离线", self.app.pron_recognized._text)

    def test_render_score_none(self):
        self.app._render_score(None)
        self.assertIn("失败", self.app.pron_result._text)

    def test_do_score_calls_scorer(self):
        captured = {"ran": False}
        class FakeThread:
            def __init__(self, target=None, daemon=None):
                self.target = target
            def start(self):
                captured["ran"] = True
                if self.target:
                    self.target()
        self.app.pron_target = FakeLabel(text="hello world")
        fake_result = {"score": 88, "accuracy": 100, "completeness": 100, "fluency": 90,
                       "quality": 80, "recognized": "hello world", "missing": [],
                       "feedback": "", "offline": False}
        with patch("threading.Thread", FakeThread), \
             patch.object(self.app.scorer, "score", return_value=fake_result) as mocked:
            self.app._do_score()
        self.assertTrue(captured["ran"])
        mocked.assert_called_once()

    def test_asr_settings_persist_to_config(self):
        cfg_path = "config.json"
        backup = None
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                backup = f.read()
        try:
            from asr import ASRConfig
            new_cfg = ASRConfig(backend="whisper", api_key="test-key-123",
                                endpoint="https://api.openai.com")
            data = {"asr": {"backend": new_cfg.backend, "api_key": new_cfg.api_key,
                            "endpoint": new_cfg.endpoint}}
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            reloaded = ASRConfig(config_path=cfg_path)
            self.assertEqual(reloaded.backend, "whisper")
            self.assertEqual(reloaded.api_key, "test-key-123")
            self.assertTrue(reloaded.is_real())
        finally:
            if backup is not None:
                with open(cfg_path, "w", encoding="utf-8") as f:
                    f.write(backup)
            elif os.path.exists(cfg_path):
                os.remove(cfg_path)


if __name__ == "__main__":
    if not HAS_TK:
        print("SKIP: tkinter 未安装，GUI 集成测试跳过（核心 ASR 逻辑见 test_asr.py）")
        sys.exit(0)
    unittest.main(verbosity=2)
