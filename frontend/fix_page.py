# -*- coding: utf-8 -*-
import os

with open("app/page.tsx", "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

# Replace any escaped quote artifacts at start
content = content.replace('\\"use client\\";', '"use client";')
content = content.replace('\\"', '"')

with open("app/page.tsx", "w", encoding="utf-8") as f:
    f.write(content)

print("app/page.tsx cleaned up, starts with:", content[:40])
