# -*- coding: utf-8 -*-
"""GUI 冒烟测试：在虚拟显示中启动应用，截图各页面后自动关闭。"""
import os, sys
import tkinter as tk

# 真实 GUI 测试，需在虚拟显示环境运行
import ai_english_app as app

root = app.EnglishApp()
root.update_idletasks()

pages = [
    ("flashcard", root._page_flashcard),
    ("chat", root._page_chat),
    ("pronunciation", root._page_pronunciation),
    ("quiz", root._page_quiz),
    ("stats", root._page_stats),
]
os.makedirs("/data/workspace/shots", exist_ok=True)

for name, builder in pages:
    root._switch_page(builder)
    root.update()
    path = f"/data/workspace/shots/{name}.png"
    # 用 pillow 通过 grab 截图；tk 8.6+ 支持
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(bbox=(0,0,960,680))
        img.save(path)
    except Exception as e:
        print("screenshot skip:", e)
    print("rendered", name)

root.destroy()
print("GUI smoke test OK")
