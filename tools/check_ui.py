#!/usr/bin/env python3
"""Optional local browser smoke test; start desktop_demo.py first. Requires Playwright."""
from pathlib import Path
import json
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width':1440,'height':1180},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8765')
    page.wait_for_function("document.getElementById('connection').textContent==='运行中'")
    box = page.locator('#map').bounding_box()
    page.locator('#map').click(position={'x':box['width']*.8,'y':box['height']*.3})
    assert float(page.locator('#x').input_value())>0
    page.locator('#id').fill('browser-smoke')
    page.locator('#priority').fill('80')
    page.locator('button.primary').click()
    page.wait_for_function("document.getElementById('log').textContent.includes('browser-smoke')")
    page.get_by_role('button',name='暂停',exact=True).click()
    page.wait_for_function("document.getElementById('state').textContent==='PAUSED'")
    page.get_by_role('button',name='继续',exact=True).click()
    page.wait_for_function("document.getElementById('state').textContent!=='PAUSED'")
    output = ROOT/'docs/images'
    output.mkdir(exist_ok=True)
    page.screenshot(path=str(output/'control_panel.png'),full_page=True)
    page.set_viewport_size({'width':430,'height':900})
    page.screenshot(path=str(output/'control_panel_mobile.png'),full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'mobile overflow'
    assert not errors,errors
    (ROOT/'test_results/ui_smoke.json').write_text(json.dumps(dict(result='PASS',errors=errors,
        cases=['state updates','map selection','incident submit','pause','resume','desktop layout','mobile layout']),indent=2),encoding='utf-8')
    browser.close()
    print('PASS: browser interaction and responsive layout')
