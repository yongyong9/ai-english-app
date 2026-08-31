# 🚀 GitHub 自动打包使用指南（小白专用）

本项目已配置 **GitHub Actions**：你只需要把代码上传到 GitHub，**点一下按钮**，云端就会自动帮你打包出 `.exe`，无需本地安装 Python。

---

## ✨ 效果

- 不用装 Python
- 不用装 PyInstaller
- 不用懂命令行
- 云端 2-3 分钟自动出成品 exe
- exe 可在任意 Windows 电脑双击运行

---

## 📦 操作步骤（跟着做就行）

### 第 1 步：注册 GitHub

打开 https://github.com ，注册一个账号（免费）。

### 第 2 步：新建仓库

1. 登录后，右上角点 `+` → **New repository**
2. 仓库名填：`ai-english-app`（随便起也行）
3. **不要**勾选 "Add a README file"（我们用已有的）
4. 点 **Create repository**

### 第 3 步：上传代码

**最简单方式（推荐新手）：**

1. 仓库页面点 **Add file** → **Upload files**
2. 把本压缩包解压后的 **整个文件夹内容** 拖拽上传
3. 拉到底点 **Commit changes**

> 💡 进阶方式（用 Git 命令行）：
> ```bash
> git init
> git add .
> git commit -m "init"
> git remote add origin https://github.com/你的用户名/ai-english-app.git
> git push -u origin main
> ```

### 第 4 步：触发打包

**方法 A：手动触发（最简单，推荐）**

1. 打开你的仓库页面
2. 点上方 **Actions** 标签
3. 左侧列表点 **Build EXE**
4. 右侧点 **Run workflow** → 再次 **Run workflow**
5. 等 2-3 分钟

**方法 B：打版本标签触发（自动）**

```bash
git tag v1.0
git push origin v1.0
```

### 第 5 步：下载 exe

- **方法 A**：Actions 页面 → 点进刚才的 run → 底部 **Artifacts** 下载 `AI学英语.exe`
- **方法 B**：仓库 **Releases** 页面直接下载

### 第 6 步：运行

下载的 `AI学英语.exe` 放到任意文件夹，**双击即可运行**，无需安装任何东西。

---

## 🔧 工作原理

每次触发时，GitHub 会启动一台 **Windows 云电脑**，自动执行：

```
1. 下载你的代码
2. 安装 Python 3.11
3. pip install -r requirements.txt
4. pyinstaller 打包成单个 exe
5. 把 exe 上传到 Artifacts / Releases
```

整个过程你看不到命令行，只需要点几下。

---

## ⚙️ 配置文件说明

| 文件 | 作用 |
|------|------|
| `.github/workflows/build.yml` | 自动打包工作流（核心） |
| `setup_github.py` | 本地检查脚本，双击或运行可验证配置是否完整 |
| `requirements.txt` | 依赖清单 |
| `build.bat` | Windows 本地一键打包（备用） |

---

## ❓ 常见问题

**Q：一定要用 GitHub 吗？**
A：这个工作流基于 GitHub Actions。如果你想完全本地打包，双击 `build.bat` 即可（需先装 Python）。

**Q：exe 能在没有网络的电脑运行吗？**
A：可以，exe 是独立的可执行文件，无需联网。

**Q：打包要钱吗？**
A：GitHub Actions 对个人免费（每月 2000 分钟额度，打包一次只用约 3 分钟）。

**Q：怎么更新版本？**
A：修改代码后再次推送，重复第 4-5 步即可。或用方法 B 打新 tag（v1.1、v1.2...）。

---

## 🆘 卡住了怎么办

按顺序检查：
1. 代码是否完整上传（仓库里能看到 `ai_english_app.py`、`.github` 文件夹）
2. Actions 页面是否显示绿色对勾（红色说明打包失败，点进去看日志）
3. Artifacts 只在 workflow 运行成功后才出现

仍无法解决可截图发我，我帮你排查。
