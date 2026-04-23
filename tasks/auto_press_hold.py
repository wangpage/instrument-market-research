"""尝试自动化 Walmart PerimeterX 的 PRESS & HOLD 验证"""
import asyncio
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright


async def find_press_hold_button(page):
    """PerimeterX 的 press-hold 通常在 iframe 里的一个 button/canvas"""
    # 1) 先看是不是 iframe
    iframes = page.frames
    print(f"frames: {len(iframes)}")
    for f in iframes:
        print(f"  frame url: {f.url[:100]}")
    # 2) 找按钮 selectors
    selectors = [
        "button[aria-label*='human' i]",
        "button:has-text('PRESS')",
        "button:has-text('Press')",
        "div[role='button']",
        "#px-captcha button",
        "#px-captcha",
        "[data-testid*='captcha']",
    ]
    # 先在主 frame
    for sel in selectors:
        try:
            el = await page.query_selector(sel)
            if el:
                box = await el.bounding_box()
                if box:
                    return page, el, box, sel
        except Exception:
            pass
    # 再 iframe
    for f in iframes:
        for sel in selectors:
            try:
                el = await f.query_selector(sel)
                if el:
                    box = await el.bounding_box()
                    if box:
                        return f, el, box, sel
            except Exception:
                pass
    return None, None, None, None


async def press_and_hold(page, button_center_x, button_center_y, duration=10.0):
    """按住按钮指定秒数，期间鼠标微动模拟人类"""
    # 先移到按钮附近（带轨迹）
    for _ in range(3):
        x = button_center_x + random.randint(-20, 20)
        y = button_center_y + random.randint(-20, 20)
        await page.mouse.move(x, y, steps=random.randint(5, 10))
        await asyncio.sleep(random.uniform(0.15, 0.35))
    # 移到中心并按下
    await page.mouse.move(button_center_x, button_center_y, steps=8)
    await asyncio.sleep(0.2)
    print(f"  按下: ({button_center_x:.0f}, {button_center_y:.0f})")
    await page.mouse.down()
    start = asyncio.get_event_loop().time()
    # 按住期间持续微动（1-3 像素）
    while asyncio.get_event_loop().time() - start < duration:
        dx = random.uniform(-2, 2)
        dy = random.uniform(-2, 2)
        await page.mouse.move(button_center_x + dx, button_center_y + dy, steps=2)
        await asyncio.sleep(random.uniform(0.1, 0.3))
    await page.mouse.up()
    print(f"  松开（共按 {duration}s）")


async def main():
    pw = await async_playwright().start()
    b = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = b.contexts[0]
    p = await ctx.new_page()

    # 触发 Walmart captcha（访问一个 search URL）
    print(">>> 访问 Walmart search 触发 captcha...")
    await p.goto("https://www.walmart.com/search?q=guitar", timeout=45000)
    await asyncio.sleep(3)
    print(f"  URL: {p.url}")

    if "blocked" not in p.url:
        print("  ✅ 未触发 captcha，直接通过")
        await p.close()
        await pw.stop()
        return

    # 找 PRESS & HOLD 按钮
    await asyncio.sleep(2)
    target_frame, btn, box, sel = await find_press_hold_button(p)
    if not btn:
        print("  ❌ 未找到按钮")
        # dump 页面看结构
        html = await p.content()
        Path("/tmp/walmart_captcha.html").write_text(html, encoding="utf-8")
        print(f"  HTML saved /tmp/walmart_captcha.html (size={len(html)})")
        await p.close()
        await pw.stop()
        return

    print(f"  找到按钮 selector={sel} box={box}")
    cx = box["x"] + box["width"] / 2
    cy = box["y"] + box["height"] / 2

    # 执行 PRESS & HOLD（10s）
    await press_and_hold(p, cx, cy, duration=10.0)

    # 等 page 跳转
    print(">>> 等待跳转...")
    await asyncio.sleep(5)
    print(f"  最终 URL: {p.url}")
    if "blocked" in p.url:
        print("  ❌ 未通过 — 再试 15 秒版本...")
        # 再找一次按钮（可能被刷新）
        _, btn2, box2, _ = await find_press_hold_button(p)
        if btn2 and box2:
            cx = box2["x"] + box2["width"] / 2
            cy = box2["y"] + box2["height"] / 2
            await press_and_hold(p, cx, cy, duration=15.0)
            await asyncio.sleep(5)
            print(f"  最终 URL: {p.url}")
    else:
        print("  ✅ captcha 通过！")
        print(f"  title: {(await p.title())[:60]}")

    await p.close()
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
