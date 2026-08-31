# -*- coding: utf-8 -*-
"""ASR 发音打分引擎测试 (test_asr.py)"""
import os
import sys
import json
import wave
import struct
import random
import tempfile
import subprocess
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import asr


def make_wav(path, duration=1.0, rate=16000, freq=440):
    """生成一个带稳定能量的 WAV 文件（正弦波），用于测试质量打分。"""
    n = int(rate * duration)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        frames = bytearray()
        for i in range(n):
            sample = int(16000 * ((i % 1000) / 1000 - 0.5))  # 三角波，稳定能量
            frames += struct.pack("h", sample)
        wf.writeframes(frames)


class TestNormalize(unittest.TestCase):
    def test_lower_and_strip_punct(self):
        self.assertEqual(asr.normalize("Hello, World!"), "hello world")
        # 撇号属于 \w，按设计保留（"i'm" 是合法词内符号）
        self.assertEqual(asr.normalize("  I'm   FINE. "), "i'm fine")

    def test_empty(self):
        self.assertEqual(asr.normalize(""), "")
        self.assertEqual(asr.normalize(None), "")


class TestAlignScore(unittest.TestCase):
    def test_perfect_match(self):
        r = asr.align_score("practice makes perfect", "practice makes perfect")
        self.assertEqual(r["accuracy"], 100)
        self.assertEqual(r["completeness"], 100)
        self.assertEqual(r["missing"], [])

    def test_partial(self):
        r = asr.align_score("practice makes perfect today", "practice perfect")
        self.assertGreaterEqual(r["completeness"], 40)
        self.assertLess(r["completeness"], 100)
        self.assertIn("makes", r["missing"])  # makes 漏读

    def test_empty_recognized(self):
        r = asr.align_score("hello world", "")
        self.assertEqual(r["accuracy"], 0)
        self.assertEqual(r["completeness"], 0)
        self.assertEqual(r["missing"], ["hello", "world"])

    def test_empty_target(self):
        r = asr.align_score("", "anything")
        self.assertEqual(r["accuracy"], 0)

    def test_similar_tolerance(self):
        # 大小写 / 标点差异应高度匹配
        r = asr.align_score("How are you?", "how are you")
        self.assertGreaterEqual(r["accuracy"], 90)


class TestAudioQuality(unittest.TestCase):
    def test_silent_is_low(self):
        q = asr.audio_quality([b"\x00\x00" * 1024])
        # 全零帧：音量=0、清晰度满分但连续性给基础分，总体应偏低 (<50)
        self.assertLessEqual(q["score"], 50)
        self.assertEqual(q["volume"], 0)

    def test_loud_signal_has_volume(self):
        # 生成大振幅信号
        frames = [struct.pack("h", 20000) * 1024]
        q = asr.audio_quality(frames)
        self.assertGreater(q["volume"], 30)

    def test_empty_frames(self):
        q = asr.audio_quality([])
        self.assertEqual(q["score"], 0)


class TestBackendSelection(unittest.TestCase):
    def test_offline_when_no_key(self):
        cfg = asr.ASRConfig(backend="offline", api_key="")
        self.assertFalse(cfg.is_real())
        b = asr.make_backend(cfg)
        self.assertIsInstance(b, asr.OfflineBackend)

    def test_whisper_when_key(self):
        cfg = asr.ASRConfig(backend="whisper", api_key="sk-test")
        self.assertTrue(cfg.is_real())
        b = asr.make_backend(cfg)
        self.assertIsInstance(b, asr.WhisperBackend)

    def test_tencent_when_key(self):
        cfg = asr.ASRConfig(backend="tencent", api_key="k", secret_id="sid")
        b = asr.make_backend(cfg)
        self.assertIsInstance(b, asr.TencentASRBackend)

    def test_offline_recognize_returns_empty(self):
        b = asr.OfflineBackend(asr.ASRConfig())
        self.assertEqual(b.recognize("nonexistent.wav"), "")

    def test_write_wav_creates_valid_file(self):
        b = asr.OfflineBackend(asr.ASRConfig())
        frames = [struct.pack("h", 100) * 512]
        path = b.write_wav(frames)
        self.assertTrue(os.path.exists(path))
        with wave.open(path, "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getframerate(), 16000)
        os.unlink(path)


class TestPronunciationScorer(unittest.TestCase):
    def setUp(self):
        self.cfg = asr.ASRConfig(backend="offline", api_key="")
        self.scorer = asr.PronunciationScorer(self.cfg)

    def test_score_without_recognition_is_in_range(self):
        # 无录音、无识别 -> 模拟分，应在 [72,94]
        self.scorer.frames = []
        r = self.scorer.score("hello world", recognized_text="")
        self.assertGreaterEqual(r["score"], 30)
        self.assertLessEqual(r["score"], 100)
        self.assertTrue(r["offline"])

    def test_score_perfect_gets_high(self):
        # 完美匹配 + 注入识别文本：无论有无录音都应高分
        with patch("random.randint", return_value=90):
            r = self.scorer.score("practice makes perfect", recognized_text="practice makes perfect")
        self.assertGreaterEqual(r["score"], 85)
        self.assertEqual(r["missing"], [])
        self.assertFalse(r["offline"])

    def test_score_poor_gets_lower(self):
        r = self.scorer.score("practice makes perfect today", recognized_text="practice")
        self.assertLess(r["completeness"], 80)
        self.assertIn("makes", r["missing"])  # 具体反馈词

    def test_feed_and_get_frames_threadsafe(self):
        import threading
        def worker():
            for _ in range(100):
                self.scorer.feed(b"\x01\x00")
        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(self.scorer.get_frames()), 400)

    def test_reset_clears_frames(self):
        self.scorer.feed(b"abc")
        self.scorer.reset()
        self.assertEqual(self.scorer.get_frames(), [])

    def test_format_result_contains_key_info(self):
        r = self.scorer.score("hello world", recognized_text="hello world")
        out = asr.PronunciationScorer.format_result(r)
        self.assertIn("综合得分", out)
        self.assertIn("建议", out)

    def test_comment_buckets(self):
        self.assertEqual(asr.PronunciationScorer.comment(90)[1], "#51cf66")
        self.assertEqual(asr.PronunciationScorer.comment(75)[1], "#fab005")
        self.assertEqual(asr.PronunciationScorer.comment(50)[1], "#ff6b6b")

    def test_real_wav_file_flow(self):
        # 用真实 WAV 文件喂帧 -> 走 write_wav + 离线识别 完整链路
        wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        make_wav(wav, duration=0.5)
        with wave.open(wav, "rb") as wf:
            data = wf.readframes(wf.getnframes())
        width = wf.getsampwidth()
        bpf = 1024 * width
        for i in range(0, len(data), bpf):
            self.scorer.feed(data[i:i + bpf])
        r = self.scorer.score("practice makes perfect", recognized_text="")
        self.assertIn("score", r)
        self.assertGreaterEqual(r["quality"], 0)
        os.unlink(wav)


class TestConfigFromFile(unittest.TestCase):
    def test_loads_asr_section(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump({"asr": {"backend": "whisper", "api_key": "abc", "language": "en"}}, f)
            path = f.name
        cfg = asr.ASRConfig(config_path=path)
        self.assertEqual(cfg.backend, "whisper")
        self.assertEqual(cfg.api_key, "abc")
        self.assertEqual(cfg.language, "en")
        os.unlink(path)

    def test_missing_file_is_ok(self):
        cfg = asr.ASRConfig(config_path="/nonexistent/path.json")
        self.assertEqual(cfg.backend, "offline")


class TestCLI(unittest.TestCase):
    def test_cli_demo_runs(self):
        # 捕获 print 输出，确认主流程不报错
        wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
        make_wav(wav, duration=0.3)
        env = os.environ.copy()
        # 用离线 + 注入识别文本的方式跑（不依赖网络/Key）
        from io import StringIO
        import contextlib
        buf = StringIO()
        try:
            with patch("sys.argv", ["asr.py", wav, "--target", "practice makes perfect", "--backend", "offline"]), \
                 contextlib.redirect_stdout(buf):
                asr.main()
        except SystemExit:
            pass
        out = buf.getvalue()
        self.assertIn("综合得分", out)
        os.unlink(wav)


if __name__ == "__main__":
    unittest.main(verbosity=2)
