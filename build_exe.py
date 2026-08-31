"""
打包 AI 学英语 App 为 Windows .exe (单文件)

使用方法:
    python build_exe.py

依赖:
    pip install pyinstaller

说明:
    在 Windows 上运行本脚本即可生成 exe。
    若在其它平台运行,只会做语法/结构检查,无法产出真正的 exe。
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
APP_NAME = "AI学英语"
ENTRY = HERE / "ai_english_app.py"

# 打包时需要额外包含的数据文件/目录 (源路径, 打包内的相对路径)
ADDED_FILES = [
    ("config.example.json", "."),
    ("README.md", "."),
]


def check_environment():
    if os.name != "nt":
        print("[!] 警告: 当前不是 Windows 系统, 无法生成真正的 .exe。")
        print("    本脚本将在 Windows 上运行时调用 PyInstaller 产出 exe。")
        print("    现在仅做项目结构与依赖检查。\n")
        return False
    return True


def run_checks():
    print("==> 检查项目结构 ...")
    required = [
        "ai_english_app.py",
        "engine.py",
        "llm.py",
        "asr.py",
        "gui_llm_bridge.py",
        "config.example.json",
    ]
    missing = [f for f in required if not (HERE / f).exists()]
    if missing:
        print("  [x] 缺少文件:", missing)
        sys.exit(1)
    print("  [ok] 核心文件齐全")

    # 语法编译检查
    py_files = list(HERE.glob("*.py"))
    for f in py_files:
        src = f.read_text(encoding="utf-8")
        compile(src, str(f), "exec")  # 校验语法, 失败会抛出 SyntaxError
    print(f"  [ok] {len(py_files)} 个 Python 文件语法检查通过")


def ensure_pyinstaller():
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        print("==> 未安装 PyInstaller, 正在尝试安装 ...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        return True


def build_icon():
    """若没有图标则生成一个简易 ico, 避免打包失败。"""
    icon = HERE / "app.ico"
    if icon.exists():
        return str(icon)
    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGBA", (256, 256), (52, 152, 219, 255))
        draw = ImageDraw.Draw(img)
        # 画一个简洁的 "A" 字母代表学英语
        font = None
        for fp in ["arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
            try:
                font = ImageFont.truetype(fp, 180)
                break
            except Exception:
                continue
        if font is None:
            font = ImageFont.load_default()
        draw.text((78, 40), "A", fill=(255, 255, 255, 255), font=font)
        img.save(icon, sizes=[(256, 256)])
        print("  [ok] 已生成默认图标 app.ico")
        return str(icon)
    except Exception as e:
        print("  [!] 无法生成图标:", e, "将不使用图标")
        return None


def build():
    print("==> 开始打包 ...")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",           # 单文件 exe
        "--windowed",          # 无控制台窗口 (GUI)
        "--name", APP_NAME,
    ]
    icon = build_icon()
    if icon:
        cmd += ["--icon", icon]

    for src, dst in ADDED_FILES:
        if (HERE / src).exists():
            cmd += ["--add-data", f"{src}{os.pathsep}{dst}"]

    cmd.append(str(ENTRY))

    print("  命令:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=HERE)
    print("\n==> 打包完成!")


def main():
    run_checks()
    is_windows = check_environment()

    dist = HERE / "dist" / f"{APP_NAME}.exe"
    if is_windows:
        ensure_pyinstaller()
        build()
        if dist.exists():
            size = dist.stat().st_size / (1024 * 1024)
            print(f"\n[✓] 产物: {dist}  ({size:.1f} MB)")
            print("    双击即可运行, 无需安装 Python。")
    else:
        print("\n==> 非 Windows 环境, 跳过实际打包。")
        print("    请在 Windows 上执行:  python build_exe.py")
        if (HERE / "dist").exists():
            for p in (HERE / "dist").glob("*"):
                print(f"      (已存在遗留产物) {p}")


if __name__ == "__main__":
    main()
