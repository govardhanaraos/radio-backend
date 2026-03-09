"""
Run this script ONCE to confirm the new Blomp login page works correctly.
It will print all inputs, buttons, and iframes found on the page.

Usage:
    python debug_blomp_login.py
"""

import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

# ✅ UPDATED URL — old dashboard.blomp.com/login returns 404
BLOMP_LOGIN_URL = "https://www3.blomp.com/login/"


def debug_blomp():
    chrome_options = Options()
    # Non-headless so you can see the page visually
    # chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        print(f">>> Navigating to: {BLOMP_LOGIN_URL}")
        driver.get(BLOMP_LOGIN_URL)

        WebDriverWait(driver, 30).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        time.sleep(3)  # Allow JS frameworks to finish mounting

        print(f"\n>>> Current URL : {driver.current_url}")
        print(f">>> Page title  : {driver.title}")

        # --- Iframes ---
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print(f"\n>>> Found {len(iframes)} iframe(s)")
        for i, f in enumerate(iframes):
            print(f"    [{i}] id='{f.get_attribute('id')}' src='{f.get_attribute('src')}'")

        # --- Inputs in top frame ---
        print("\n>>> INPUT elements (top frame):")
        inputs = driver.find_elements(By.TAG_NAME, "input")
        if inputs:
            for inp in inputs:
                print(f"    type='{inp.get_attribute('type')}' "
                      f"name='{inp.get_attribute('name')}' "
                      f"id='{inp.get_attribute('id')}' "
                      f"placeholder='{inp.get_attribute('placeholder')}'")
        else:
            print("    (none)")

        # --- Inputs inside iframes ---
        for i, frame in enumerate(iframes):
            try:
                driver.switch_to.frame(frame)
                inputs_in_frame = driver.find_elements(By.TAG_NAME, "input")
                print(f"\n>>> INPUT elements inside iframe[{i}]:")
                if inputs_in_frame:
                    for inp in inputs_in_frame:
                        print(f"    type='{inp.get_attribute('type')}' "
                              f"name='{inp.get_attribute('name')}' "
                              f"id='{inp.get_attribute('id')}' "
                              f"placeholder='{inp.get_attribute('placeholder')}'")
                else:
                    print("    (none)")
                driver.switch_to.default_content()
            except Exception as e:
                print(f"    Could not inspect iframe[{i}]: {e}")
                driver.switch_to.default_content()

        # --- Buttons ---
        print("\n>>> BUTTON elements:")
        for btn in driver.find_elements(By.TAG_NAME, "button"):
            print(f"    type='{btn.get_attribute('type')}' "
                  f"class='{btn.get_attribute('class')}' "
                  f"text='{btn.text[:80]}'")

        # --- Page source ---
        print("\n>>> Page source (first 2000 chars):")
        print(driver.page_source[:2000])

        print("\n>>> Done. Sleeping 15s for manual inspection...")
        time.sleep(15)

    finally:
        driver.quit()


if __name__ == "__main__":
    debug_blomp()