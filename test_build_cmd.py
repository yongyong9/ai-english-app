"""
验证 build_exe.build() 拼装的 PyInstaller 命令是否正确。
在 Linux 沙盒中不真正调用 PyInstaller, 而是 mock subprocess.check_call
来捕获并打印最终命令, 同时校验各参数。
"""
import os
import sys
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_exe

captured = {}

def fake_check_call(cmd, cwd=None):
    captured["cmd"] = cmd
    captured["cwd"] = cwd
    return 0

# 让 build() 认为产物已生成, 以走完成功分支
def fake_dist_exists(self):
    # self 是 Path 实例
    if str(self).endswith(".exe"):
        return True
    return os.path.exists(self)

with patch("build_exe.subprocess.check_call", side_effect=fake_check_call), \
     patch("build_exe.ensure_pyinstaller", return_value=True), \
     patch("build_exe.Path.exists", autospec=True, side_effect=fake_dist_exists):
    # 伪装成 Windows, 触发真实 build() 逻辑
    with patch("os.name", "nt"):
        build_exe.build()

cmd = captured.get("cmd", [])
print("\n===== 拼装的 PyInstaller 命令 =====")
print(" ".join(str(c) for c in cmd))
print("===================================\n")

# 断言关键参数
checks = [
    ("onefile", "--onefile" in cmd),
    ("windowed", "--windowed" in cmd),
    ("name", "--name" in cmd),
    ("icon", "--icon" in cmd),
    ("add-data config", any("config.example.json" in str(c) for c in cmd)),
    ("entry point", str(HERE / "ai_english_app.py") in [str(c) for c in cmd]),
]
ok = True
for name, cond in checks:
    print(f"  [{'ok' if cond else 'x'}] {name}")
    ok = ok and cond

# --add-data 分隔符在 Windows 应为 ;
if any("config.example.json" in str(c) for c in cmd):
    sep_ok = any(str(c).startswith("config.example.json") and os.pathsep in str(c) for c in cmd)
    print(f"  [{'ok' if sep_ok else 'x'}] add-data 使用正确分隔符(os.pathsep)")
    ok = ok and sep_ok

print("\n结果:", "全部通过 ✅" if ok else "存在问题 ❌")
sys.exit(0 if ok else 1)
