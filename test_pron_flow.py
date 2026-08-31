# -*- coding: utf-8 -*-
"""
跟读打分 端到端链路测试（无需 tkinter / 麦克风）
==============================================
用"与 GUI 等价的逻辑"模拟 EnglishApp 的跟读页，真实验证：
  录音帧 -> scorer.feed() -> scorer.score(target) -> _render_score()
覆盖：完美/部分/离线降级/无帧 四种场景 + config 持久化。
"""
import os
import sys
import json
import struct
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asr


class FakeLabel:
    """对应 GUI 里的 tk.Label，只记录最后设置的 text。"""
    def __init__(self):
        self.text = ""
    def config(self, **kw):
        if "text" in kw:
            self.text = kw["text"]


class FakeApp:
    """复刻 ai_english_app 跟读页打分相关方法（逻辑完全一致）。"""
    def __init__(self, config=None):
        self.scorer = asr.PronunciationScorer(config=config or asr.ASRConfig())
        self.pron_target = FakeLabel()
        self.pron_result = FakeLabel()
        self.pron_detail = FakeLabel()
        self.pron_recognized = FakeLabel()

    def _render_score(self, result):
        if not result:
            self.pron_result.text = "评分失败，请重试"
            return
        comment, color = asr.PronunciationScorer.comment(result["score"])
        self.pron_result.text = f"综合得分：{result['score']} 分 — {comment}"
        self.pron_detail.text = (
            f"文本准确率 {result['accuracy']}  ·  完整度 {result['completeness']}  "
            f"·  流畅度 {result['fluency']}  ·  音频质量 {result['quality']}")
        if result.get("recognized"):
            self.pron_recognized.text = f"识别结果：{result['recognized']}"
        elif result.get("offline"):
            self.pron_recognized.text = "（离线模式：未配置 ASR，分数基于音频质量估算）"

    def feed_frames(self, pcm_frames):
        for f in pcm_frames:
            self.scorer.feed(f)

    def score_current(self, target, recognized=None):
        return self.scorer.score(target, recognized_text=recognized)


class TestPronunciationFlow(unittest.TestCase):
    def setUp(self):
        self.app = FakeApp(asr.ASRConfig(backend="offline"))

    def _make_frames(self, amp=10000, n=40):
        """生成稳定能量的 PCM 帧（模拟正常说话音量）。"""
        return [struct.pack("h", amp) * 1024 for _ in range(n)]

    def test_flow_perfect_with_real_frames(self):
        # 场景1：有录音 + 注入完美识别文本 -> 高分 + 全字段渲染
        self.app.pron_target.text = "practice makes perfect"
        self.app.feed_frames(self._make_frames())
        result = self.app.score_current("practice makes perfect",
                                        recognized="practice makes perfect")
        self.app._render_score(result)
        self.assertIn("95", self.app.pron_result.text)  # 综合分（满分100加权后95）
        self.assertIn("准确率 100", self.app.pron_detail.text)  # 文本准确率100
        self.assertIn("准确", self.app.pron_detail.text)
        self.assertIn("practice makes perfect", self.app.pron_recognized.text)

    def test_flow_partial_recognition(self):
        # 场景2：识别文本只覆盖部分 -> 完整度低、有漏读提示
        self.app.pron_target.text = "practice makes perfect today"
        self.app.feed_frames(self._make_frames())
        result = self.app.score_current("practice makes perfect today",
                                        recognized="practice perfect")
        self.app._render_score(result)
        self.assertLess(result["completeness"], 100)
        self.assertIn("makes", result["missing"])

    def test_flow_offline_no_recognition(self):
        # 场景3：有录音但 ASR 未返回文本（离线降级）-> 走能量打分
        self.app.pron_target.text = "hello world"
        self.app.feed_frames(self._make_frames(amp=20000))
        with patch("random.randint", return_value=80):
            result = self.app.score_current("hello world", recognized="")
        self.app._render_score(result)
        self.assertTrue(result["offline"])
        self.assertIn("离线", self.app.pron_recognized.text)
        self.assertGreaterEqual(result["score"], 30)

    def test_flow_no_frames_simulation(self):
        # 场景4：无录音（模拟/演示模式）-> 返回 72-94 区间
        self.app.pron_target.text = "hello"
        result = self.app.score_current("hello", recognized="")
        self.assertGreaterEqual(result["score"], 72)
        self.assertLessEqual(result["score"], 94)

    def test_flow_real_backend_alignment(self):
        # 场景5：构造一个 WhisperBackend 实例，mock 其 recognize 方法返回目标文本，
        # 喂入真实 PCM 帧 -> scorer 走"有识别结果"对齐分支 -> 高分
        self.app.scorer = asr.PronunciationScorer(
            config=asr.ASRConfig(backend="whisper", api_key="sk-test"))
        self.app.scorer.backend = MagicLike("practice makes perfect")
        self.app.pron_target.text = "practice makes perfect"
        self.app.feed_frames(self._make_frames())
        result = self.app.scorer.score("practice makes perfect")  # recognized=None -> 调 backend
        self.app._render_score(result)
        self.assertGreaterEqual(result["score"], 85)
        self.assertEqual(result["missing"], [])
        self.assertFalse(result["offline"])

    def test_flow_save_settings_to_config(self):
        # 场景6：保存 ASR 设置到 config.json，重新加载后生效（复刻 GUI 设置弹窗逻辑）
        cfg_path = "config.json"
        backup = None
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                backup = f.read()
        try:
            data = {"asr": {"backend": "tencent", "api_key": "tencent-key",
                            "secret_id": "sid", "region": "ap-guangzhou"}}
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            cfg = asr.ASRConfig(config_path=cfg_path)
            self.assertEqual(cfg.backend, "tencent")
            self.assertTrue(cfg.is_real())
            self.assertIsInstance(asr.make_backend(cfg), asr.TencentASRBackend)
        finally:
            if backup is not None:
                with open(cfg_path, "w", encoding="utf-8") as f:
                    f.write(backup)
            elif os.path.exists(cfg_path):
                os.remove(cfg_path)


class MagicLike:
    """极简替身：让 backend.recognize() 返回指定文本，write_wav 返回临时文件。"""
    def __init__(self, text):
        self._text = text
    def recognize(self, wav_path):
        return self._text
    def write_wav(self, frames):
        import tempfile
        return tempfile.NamedTemporaryFile(suffix=".wav", delete=True).name


if __name__ == "__main__":
    unittest.main(verbosity=2)
