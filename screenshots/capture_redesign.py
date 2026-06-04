#!/usr/bin/env python3
"""Capture screenshots of the redesigned Construct AI Agent UI."""

import os
import time
import threading
import http.server
import functools
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "/home/z/my-project/screenshots_redesign"
SERVE_DIR = "/home/z/construct-ai-agent/dist"
PORT = 4175
BASE_URL = f"http://127.0.0.1:{PORT}"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Start HTTP server
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=SERVE_DIR)
httpd = http.server.HTTPServer(("127.0.0.1", PORT), handler)
server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
server_thread.start()
print(f"HTTP server started on {BASE_URL}")

def take_screenshot(page, name):
    path = os.path.join(OUTPUT_DIR, f"{name}.png")
    page.screenshot(path=path)
    size_kb = os.path.getsize(path) / 1024
    print(f"  SAVED: {name}.png ({size_kb:.0f} KB)")
    return path

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        device_scale_factor=2,
    )
    
    # ─── SCREENSHOT 1: Splash Screen ───
    print("\n[1/6] Splash Screen")
    page = context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded")
    time.sleep(1)
    take_screenshot(page, "01_splash_screen")
    page.close()
    
    # ─── Load Main App ───
    print("\nLoading Main App...")
    page = context.new_page()
    page.add_init_script("localStorage.setItem('construct_onboarding_complete', 'true');")
    page.goto(BASE_URL, wait_until="domcontentloaded")
    
    try:
        page.wait_for_function("""
            () => document.querySelector('aside') !== null || document.querySelector('main') !== null
        """, timeout=30000)
        print("  Main app loaded!")
    except:
        print("  Timeout waiting for main app")
    time.sleep(4)
    
    # ─── SCREENSHOT 2: Full IDE with Right Panel ───
    print("\n[2/6] Full IDE - Cursor Style Layout")
    take_screenshot(page, "02_full_ide_cursor_style")
    
    # ─── SCREENSHOT 3: Right Panel - Chat Tab ───
    print("\n[3/6] Right Panel - Chat Tab")
    page.evaluate("""() => {
        window.dispatchEvent(new CustomEvent('construct:panel-tab', { detail: 'chat' }));
    }""")
    time.sleep(0.5)
    take_screenshot(page, "03_right_panel_chat")
    
    # ─── SCREENSHOT 4: Right Panel - Agent Tab ───
    print("\n[4/6] Right Panel - Agent Tab")
    page.evaluate("""() => {
        window.dispatchEvent(new CustomEvent('construct:panel-tab', { detail: 'agent' }));
    }""")
    time.sleep(0.5)
    take_screenshot(page, "04_right_panel_agent")
    
    # ─── SCREENSHOT 5: Right Panel - Memory Tab ───
    print("\n[5/6] Right Panel - Memory Tab")
    page.evaluate("""() => {
        window.dispatchEvent(new CustomEvent('construct:panel-tab', { detail: 'memory' }));
    }""")
    time.sleep(0.5)
    take_screenshot(page, "05_right_panel_memory")
    
    # ─── SCREENSHOT 6: Command Palette ───
    print("\n[6/6] Command Palette")
    page.keyboard.press("Control+Shift+p")
    time.sleep(1)
    take_screenshot(page, "06_command_palette")
    
    page.close()
    browser.close()
    httpd.shutdown()

print(f"\nAll redesign screenshots captured!")
print(f"Saved to: {OUTPUT_DIR}")
