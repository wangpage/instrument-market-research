import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from playwright.async_api import async_playwright


async def main():
    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    for host in ["https://www.temu.com", "https://www.tiktok.com"]:
        cookies = await ctx.cookies(host)
        print(f"\n{host}: total {len(cookies)} cookies")
        login_markers = {
            "temu.com": ["api_uid", "user_uin", "login", "PassKey", "dilx"],
            "tiktok.com": ["sessionid", "sid_tt", "sid_guard", "uid_tt", "sessionid_ss"],
        }
        key = "temu.com" if "temu" in host else "tiktok.com"
        found = [c for c in cookies if c["name"] in login_markers[key]]
        if found:
            print(f"  ✅ 登录态 cookies 找到 {len(found)}:")
            for c in found:
                print(f"     {c['name']}={c['value'][:30]}...")
        else:
            print(f"  ❌ 没有登录态 cookie（说明 CDP Chrome 里未登录）")
            print(f"  前 10 个 cookie 名: {[c['name'] for c in cookies[:10]]}")
    await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
