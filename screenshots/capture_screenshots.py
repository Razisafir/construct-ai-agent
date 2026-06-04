#!/usr/bin/env python3
"""Capture comprehensive screenshots of Construct AI Agent UI using Playwright.
Starts its own HTTP server, manipulates Zustand store directly for state changes.
"""

import os
import time
import threading
import http.server
import functools
from playwright.sync_api import sync_playwright

OUTPUT_DIR = "/home/z/my-project/screenshots"
SERVE_DIR = "/home/z/construct-ai-agent/dist"
PORT = 4173
BASE_URL = f"http://127.0.0.1:{PORT}"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Start HTTP server in background thread
handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=SERVE_DIR)
httpd = http.server.HTTPServer(("127.0.0.1", PORT), handler)
server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
server_thread.start()
print(f"HTTP server started on {BASE_URL}")

def take_screenshot(page, name):
    """Take a screenshot and save to output dir."""
    path = os.path.join(OUTPUT_DIR, f"{name}.png")
    page.screenshot(path=path)
    size_kb = os.path.getsize(path) / 1024
    print(f"  SAVED: {name}.png ({size_kb:.0f} KB)")
    return path

def set_store_state(page, state_update):
    """Set Zustand store state directly via page.evaluate."""
    page.evaluate(f"""
        () => {{
            // Access Zustand store from React component tree
            // The store is accessible via module scope, we need to use window.__ZUSTAND_STORE__
            // or find another way. Let's dispatch custom events instead.
        }}
    """)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-gpu"])
    context = browser.new_context(
        viewport={"width": 1440, "height": 900},
        device_scale_factor=2,
    )
    
    # ─── SCREENSHOT 1: Splash Screen ───
    print("\n[1/10] Splash Screen")
    page = context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded")
    time.sleep(1)  # Let splash render with animated dots
    take_screenshot(page, "01_splash_screen")
    page.close()
    
    # ─── Load Main App (skip onboarding + splash) ───
    print("\nLoading Main App...")
    page = context.new_page()
    
    # Pre-set localStorage to skip onboarding
    page.add_init_script("""
        localStorage.setItem('construct_onboarding_complete', 'true');
    """)
    
    page.goto(BASE_URL, wait_until="domcontentloaded")
    # Wait for splash screen to finish
    print("  Waiting for splash to dismiss...")
    try:
        page.wait_for_function("""
            () => {
                return document.querySelector('aside') !== null || document.querySelector('main') !== null;
            }
        """, timeout=30000)
    except:
        print("  Timeout waiting for main app")
    
    time.sleep(3)  # Let lazy components load
    
    # ─── SCREENSHOT 2: Main App - Full IDE View ───
    print("\n[2/10] Main App - Full IDE View")
    # Make sure panel and sidebar are visible
    page.evaluate("""
        () => {
            // Dispatch events to show panel and sidebar
            const store = window.__ZUSTAND_STORE__ || null;
            if (store) {
                store.getState().setPanelTab('agent');
            }
        }
    """)
    take_screenshot(page, "02_main_app_full")
    
    # ─── SCREENSHOT 3: Agent Panel ───
    print("\n[3/10] Agent Panel")
    # Use window event to switch panel tab
    page.evaluate("""
        () => {
            window.dispatchEvent(new CustomEvent('construct:panel-tab', { detail: 'agent' }));
        }
    """)
    time.sleep(1)
    take_screenshot(page, "03_agent_panel")
    
    # ─── SCREENSHOT 4: Memory Panel ───
    print("\n[4/10] Memory Panel")
    page.evaluate("""
        () => {
            window.dispatchEvent(new CustomEvent('construct:panel-tab', { detail: 'memory' }));
        }
    """)
    time.sleep(1)
    take_screenshot(page, "04_memory_panel")
    
    # ─── SCREENSHOT 5: Skills Marketplace ───
    print("\n[5/10] Skills Marketplace")
    page.evaluate("""
        () => {
            window.dispatchEvent(new CustomEvent('construct:panel-tab', { detail: 'skills' }));
        }
    """)
    time.sleep(1)
    take_screenshot(page, "05_skills_marketplace")
    
    # ─── SCREENSHOT 6: MCP Connectors ───
    print("\n[6/10] MCP Connectors")
    page.evaluate("""
        () => {
            window.dispatchEvent(new CustomEvent('construct:panel-tab', { detail: 'mcp' }));
        }
    """)
    time.sleep(1)
    take_screenshot(page, "06_mcp_connectors")
    
    # ─── SCREENSHOT 7: Multi-Agent Panel ───
    print("\n[7/10] Multi-Agent Panel")
    page.evaluate("""
        () => {
            window.dispatchEvent(new CustomEvent('construct:panel-tab', { detail: 'agents' }));
        }
    """)
    time.sleep(1)
    take_screenshot(page, "07_multi_agent_panel")
    
    # ─── SCREENSHOT 8: Autonomous Mode ───
    print("\n[8/10] Autonomous Mode")
    page.evaluate("""
        () => {
            window.dispatchEvent(new CustomEvent('construct:panel-tab', { detail: 'auto' }));
        }
    """)
    time.sleep(1)
    take_screenshot(page, "08_autonomous_mode")
    
    # ─── SCREENSHOT 9: Command Palette ───
    print("\n[9/10] Command Palette")
    page.evaluate("""
        () => {
            window.dispatchEvent(new KeyboardEvent('keydown', {
                key: 'p', ctrlKey: true, shiftKey: true, bubbles: true
            }));
        }
    """)
    time.sleep(1)
    # Also try direct keyboard shortcut
    page.keyboard.press("Control+Shift+p")
    time.sleep(1)
    take_screenshot(page, "09_command_palette")
    
    # ─── SCREENSHOT 10: Settings Panel ───
    print("\n[10/10] Settings Panel")
    page.keyboard.press("Escape")
    time.sleep(0.3)
    page.keyboard.press("Control+,")
    time.sleep(2)
    take_screenshot(page, "10_settings_panel")
    
    page.close()
    
    # ─── BONUS: Onboarding Modal ───
    print("\n[BONUS] Onboarding Modal")
    page2 = context.new_page()
    # Remove onboarding flag so it shows
    page2.add_init_script("""
        localStorage.removeItem('construct_onboarding_complete');
    """)
    page2.goto(BASE_URL, wait_until="domcontentloaded")
    # Wait for splash to finish then onboarding to show
    print("  Waiting for onboarding modal...")
    try:
        page2.wait_for_function("""
            () => {
                const text = document.body.innerText || '';
                return text.includes('Welcome') || text.includes('Setup') || text.includes('Project') || text.includes('Get Started') || text.includes('step');
            }
        """, timeout=30000)
        print("  Onboarding modal appeared!")
    except:
        print("  Onboarding modal didn't appear, trying to force it")
        # Try to force onboarding by removing splash and showing modal directly
        page2.evaluate("""
            () => {
                // Force show onboarding by setting state
                const overlays = document.querySelectorAll('[class*="modal"], [class*="overlay"], [role="dialog"]');
                if (overlays.length > 0) {
                    overlays.forEach(el => el.style.display = 'block');
                }
            }
        """)
    time.sleep(1)
    take_screenshot(page2, "11_onboarding_modal")
    page2.close()
    
    # ─── BONUS: Sidebar Collapsed ───
    print("\n[BONUS] Sidebar Collapsed View")
    page3 = context.new_page()
    page3.add_init_script("""
        localStorage.setItem('construct_onboarding_complete', 'true');
    """)
    page3.goto(BASE_URL, wait_until="domcontentloaded")
    try:
        page3.wait_for_function("""
            () => document.querySelector('aside') !== null || document.querySelector('main') !== null
        """, timeout=30000)
    except:
        pass
    time.sleep(3)
    # Toggle sidebar off
    page3.keyboard.press("Control+b")
    time.sleep(0.5)
    take_screenshot(page3, "12_sidebar_collapsed")
    page3.close()
    
    browser.close()
    httpd.shutdown()

print(f"\nAll screenshots captured!")
print(f"Saved to: {OUTPUT_DIR}")
