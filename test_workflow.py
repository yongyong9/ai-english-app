"""
验证 GitHub Actions 工作流:
1. YAML 语法合法, 且 'on' 等键被保留为字符串 (避免被解析为布尔)
2. 关键步骤齐全 (checkout / setup-python / pyaudio / build_exe / upload / release)
3. 仅在 tag 时发版 (if startsWith refs/tags)
"""
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyyaml"])
    import yaml

WF = Path(__file__).parent / ".github" / "workflows" / "build-windows.yml"
text = WF.read_text(encoding="utf-8")


# --- 关键修复 ---
# PyYAML 会把 YAML 1.1 的 'on'/'off' 解析为布尔值, 导致 data['on'] -> KeyError。
# GitHub Actions 本身能正确解析, 但为了让验证脚本可靠工作,
# 我们用自定义 SafeLoader, 移除 bool 映射中 'on'/'off' 的影响。
class Loader(yaml.SafeLoader):
    pass
# 重置 bool 解析: 让 'on' 作为普通标量被解析为字符串
# 方式: 直接读取顶层结构后, 将 True/False 键还原 — 改用节点级处理:
def construct_mapping(loader, node, deep=False):
    loader.flatten_mapping(node)
    out = {}
    for k_node, v_node in node.value:
        key = loader.construct_object(k_node, deep=deep)
        val = loader.construct_object(v_node, deep=deep)
        out[key] = val
    return out

# 更简单稳妥: 用 compose + 手动解析保留字符串键
# 最终方案 —— 直接用 yaml.compose 拿到节点树, 保留原始标量类型
def load_workflow(src: str):
    """解析 workflow YAML, 保证顶层 mapping 的键为 str (on 不被转成 True)。"""
    loader = yaml.SafeLoader(src)
    try:
        node = loader.get_single_node()
    finally:
        loader.dispose()

    def to_python(n):
        if isinstance(n, yaml.MappingNode):
            d = {}
            for kn, vn in n.value:
                # 标量键统一转 str, 避免 bool 化
                if isinstance(kn, yaml.ScalarNode):
                    key = loader.construct_scalar(kn)
                else:
                    key = loader.construct_object(kn)
                d[key] = to_python(vn)
            return d
        if isinstance(n, yaml.SequenceNode):
            return [to_python(x) for x in n.value]
        if isinstance(n, yaml.ScalarNode):
            return loader.construct_scalar(n)
        return None

    return to_python(node)


data = load_workflow(text)

# 断言 'on' 是字符串键 (核心: 不被解析为 True)
assert "on" in data, f"缺少 'on' 触发配置, 实际键: {list(data.keys())}"
assert isinstance(data["on"], (dict, list)), "'on' 应为触发配置, 不应是布尔值"

jobs = data["jobs"]
assert "build" in jobs, "必须有 build job"

steps = jobs["build"]["steps"]
names = [s.get("name", "") for s in steps]

required = [
    "Checkout 源码",
    "设置 Python",
    "安装 PyAudio 预编译 wheel",
    "安装其余依赖 + PyInstaller",
    "打包为 EXE",
    "上传 exe 作为 Artifact",
    "发布到 GitHub Releases",
]
for r in required:
    assert any(r in n for n in names), f"缺少步骤: {r}"

# 发版步骤应仅在 tag 触发
release_step = next(s for s in steps if "发布到 GitHub Releases" in s.get("name", ""))
assert release_step.get("if") == "startsWith(github.ref, 'refs/tags/')", "Release 应仅限 tag"

# runner 必须是 Windows
assert jobs["build"]["runs-on"] == "windows-latest"

# 触发条件 (on 可能是 dict 或 list)
on = data["on"]
on_str = str(on)
has_dispatch = "workflow_dispatch" in on_str
has_tags = ("tags" in on) if isinstance(on, dict) else ("tags" in on_str)
assert has_dispatch, "应支持手动触发 workflow_dispatch"
assert has_tags, "应通过 push tags 触发发版"

# PyAudio 步骤不应含无关的 pytorch URL
pyaudio_step = next(s for s in steps if "Gohlke 镜像" in s.get("name", ""))
assert "pytorch" not in str(pyaudio_step), "PyAudio 步骤混入无关 URL!"

# build_exe.py 步骤必须存在且正确
build_step = next(s for s in steps if "打包为 EXE" in s.get("name", ""))
assert "python build_exe.py" in str(build_step)

print("✓ YAML 语法合法, 'on' 键正确保留为字符串 (未被解析为布尔)")
print("✓ job: build   runs-on: windows-latest")
print("✓ 步骤齐全:", len(steps), "步")
for n in names:
    print("    -", n)
print("✓ Release 仅限 tag 触发 (startsWith refs/tags/)")
print("✓ PyAudio 安装步骤干净 (无无关 URL)")
print("✓ 打包命令: python build_exe.py")
print("\n全部验证通过 ✅")
