"""
验证 build_exe.py 的项目结构检查逻辑 (不实际打包)。
"""
import sys
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

# 导入 build_exe 但不执行 main()
import build_exe

print("== 测试 run_checks() ==")
try:
    build_exe.run_checks()
    print("[ok] run_checks 通过\n")
except SystemExit as e:
    print(f"[x] run_checks 退出码: {e.code}\n")

print("== 测试 build_icon() ==")
icon_path = build_exe.build_icon()
if icon_path and os.path.exists(icon_path):
    print(f"[ok] 图标生成: {icon_path} ({os.path.getsize(icon_path)} bytes)")
else:
    print("[!] 未生成图标 (Pillow 可能不可用), 属可接受的降级")

print("\n== 验证 ADDED_FILES 引用存在 ==")
for src, dst in build_exe.ADDED_FILES:
    p = HERE / src
    print(f"  {'[ok]' if p.exists() else '[x] 缺失'} {src} -> {dst}")

print("\n所有验证完成。")
