"""
GitHub Actions 一键配置脚本（小白专用）

功能：
1. 检查/创建 .gitignore（忽略 __pycache__、dist、build 等）
2. 检查项目结构完整性
3. 提示下一步操作

运行：python setup_github.py
"""

import os
from pathlib import Path

ROOT = Path(__file__).parent
WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"

def check():
    print("=" * 50)
    print("  AI学英语 - GitHub 自动打包 配置检查")
    print("=" * 50)

    # 1. 工作流文件
    print(f"\n[1/3] 检查工作流文件...")
    if WORKFLOW.exists():
        print(f"  ✅ 已就绪: {WORKFLOW.relative_to(ROOT)}")
    else:
        print(f"  ❌ 缺失: {WORKFLOW.relative_to(ROOT)}")
        return False

    # 2. 必要文件
    print(f"\n[2/3] 检查必要文件...")
    required = [
        "ai_english_app.py",
        "requirements.txt",
        "build.bat",
        "config.example.json",
    ]
    all_ok = True
    for f in required:
        if (ROOT / f).exists():
            print(f"  ✅ {f}")
        else:
            print(f"  ❌ 缺失 {f}")
            all_ok = False

    # 3. .gitignore
    print(f"\n[3/3] 检查 .gitignore...")
    gitignore = ROOT / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(
            "\n".join([
                "__pycache__/",
                "*.pyc",
                "build/",
                "dist/",
                "*.spec",
                "config.json",
                ".venv/",
                "venv/",
            ]),
            encoding="utf-8",
        )
        print("  ✅ 已自动创建 .gitignore")
    else:
        print("  ✅ 已存在 .gitignore")

    print("\n" + "=" * 50)
    if all_ok:
        print("  ✅ 全部就绪！按下方步骤即可自动打包")
    else:
        print("  ❌ 存在缺失文件，请检查")
    print("=" * 50)

    print("""
📦 使用步骤（小白也能懂）：

  1️⃣  注册 GitHub 账号（github.com）

  2️⃣  新建仓库（右上角 + → New repository）
       名字随便起，比如 ai-english-app

  3️⃣  把整个文件夹上传到仓库
       （可用 GitHub Desktop，或网页直接拖拽上传）

  4️⃣  触发打包：
       👉 方法A（推荐新手）：网页打开仓库 → 点 Actions 标签
           → 左侧点 "Build EXE" → 点右上角 "Run workflow"
       👉 方法B（发版本）：本地执行
           git tag v1.0
           git push origin v1.0

  5️⃣  等待 2-3 分钟，exe 自动出现在：
       👉 Artifacts（方法A）
       👉 Releases（方法B）

  6️⃣  下载 .exe，双击运行，完事！
""")
    return all_ok

if __name__ == "__main__":
    check()
