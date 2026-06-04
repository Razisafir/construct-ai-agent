#!/usr/bin/env python3
"""Capture additional screenshots of Construct AI Agent UI - focused on specific panel tabs."""

import os
import time
import threading
import http.server
import functools
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "/home/z/my-project/screenshots"
SERVE_DIR = "/home/z/construct-ai-agent/dist"
PORT = 4174
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

def click_panel_tab(page, tab_text):
    """Click on a specific panel tab by its text content."""
    result = page.evaluate(f"""
        () => {{
            const tabs = document.querySelectorAll('button, [role="tab"], span');
            for (const tab of tabs) {{
                if (tab.textContent.trim().toLowerCase() === '{tab_text.lower()}') {{
                    tab.click();
                    return true;
                }}
            }}
            // Also try matching partial text
            for (const tab of tabs) {{
                if (tab.textContent.trim().toLowerCase().includes('{tab_text.lower()}')) {{
                    tab.click();
                    return true;
                }}
            }}
            return false;
        }}
    """)
    return result

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        device_scale_factor=2,
    )
    
    # Load main app
    page = context.new_page()
    page.add_init_script("localStorage.setItem('construct_onboarding_complete', 'true');")
    page.goto(BASE_URL, wait_until="domcontentloaded")
    
    print("Waiting for main app...")
    try:
        page.wait_for_function("""
            () => document.querySelector('aside') !== null || document.querySelector('main') !== null
        """, timeout=30000)
    except:
        pass
    time.sleep(4)
    
    # ─── Click on each panel tab and screenshot ───
    panel_tabs = [
        ("agent", "13_agent_panel_tab"),
        ("memory", "14_memory_panel_tab"),
        ("chat", "15_chat_panel_tab"),
        ("skills", "16_skills_panel_tab"),
        ("mcp", "17_mcp_panel_tab"),
        ("agents", "18_multi_agent_panel_tab"),
        ("auto", "19_autonomous_panel_tab"),
        ("changes", "20_changes_panel_tab"),
        ("screen", "21_screen_panel_tab"),
        ("terminal", "22_terminal_panel_tab"),
    ]
    
    for tab_name, filename in panel_tabs:
        print(f"\n[{tab_name}] Panel Tab")
        clicked = click_panel_tab(page, tab_name)
        print(f"  Clicked: {clicked}")
        time.sleep(0.8)
        take_screenshot(page, filename)
    
    # ─── Sidebar tab clicks ───
    sidebar_tabs = [
        ("files", "23_sidebar_files"),
        ("git", "24_sidebar_git"),
        ("agent", "25_sidebar_agent"),
        ("memory", "26_sidebar_memory"),
        ("skills", "27_sidebar_skills"),
        ("mcp", "28_sidebar_mcp"),
    ]
    
    for tab_name, filename in sidebar_tabs:
        print(f"\n[{tab_name}] Sidebar Tab")
        # Try clicking sidebar icon
        page.evaluate(f"""
            () => {{
                const icons = document.querySelectorAll('button, [role="tab"], div[style*="cursor"]');
                for (const icon of icons) {{
                    const title = icon.getAttribute('title') || icon.getAttribute('aria-label') || '';
                    if (title.toLowerCase().includes('{tab_name}')) {{
                        icon.click();
                        return true;
                    }}
                }}
                return false;
            }}
        """)
        time.sleep(0.5)
        take_screenshot(page, filename)
    
    page.close()
    browser.close()
    httpd.shutdown()

print(f"\nAll additional screenshots captured!")
print(f"Saved to: {OUTPUT_DIR}")
