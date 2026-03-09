import time

import psycopg2
from fastapi import BackgroundTasks, APIRouter
from selenium import webdriver
from selenium.webdriver.common.by import By
from db.db import POSTGRESQL_DATABASE_URL_TELUGUWAP, BLOMP_USER, BLOMP_PASS
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# pip install requests selenium webdriver-manager


router = APIRouter(prefix="/blomp", tags=["blomp"])

# Confirmed working login URL (dashboard.blomp.com/login returns 404)
BLOMP_LOGIN_URL = "https://www3.blomp.com/login/"


def get_db_connection():
    conn = psycopg2.connect(POSTGRESQL_DATABASE_URL_TELUGUWAP)
    return conn, conn.cursor()


def login_to_blomp(email, password):
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")

    driver = webdriver.Chrome(options=chrome_options)

    try:
        driver.get(BLOMP_LOGIN_URL)

        wait = WebDriverWait(driver, 30)
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")

        # Confirmed selectors from debug output:
        #   type='text'     name='email'    id='email'    placeholder='Email Address'
        #   type='password' name='password' id='password' placeholder='Password'
        #   button type='submit' class='loginbtn' text='LOGIN'
        #
        # NOTE: email field is type='text', NOT type='email' — use name or id instead.

        email_input = wait.until(EC.element_to_be_clickable((By.NAME, "email")))
        email_input.clear()
        email_input.send_keys(email)

        password_input = wait.until(EC.element_to_be_clickable((By.NAME, "password")))
        password_input.clear()
        password_input.send_keys(password)

        login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.loginbtn")))
        login_button.click()

        # Wait for redirect away from login page to confirm success
        wait.until(EC.url_changes(BLOMP_LOGIN_URL))
        print(f"Successfully logged in: {email} → {driver.current_url}")
        return True

    except Exception as e:
        print(f"Login failed for {email}: {str(e)[:200]}")
        return False
    finally:
        driver.quit()


def run_bulk_login(limit: int = 50):
    conn, cur = get_db_connection()
    try:
        cur.execute("""
            SELECT email, blomp_password FROM user_mail_accounts 
            WHERE last_login_date < CURRENT_DATE OR last_login_date IS NULL 
            LIMIT %s
        """, (limit,))
        accounts = cur.fetchall()

        if not accounts:
            print("No accounts need processing today.")
            return

        for email, password in accounts:
            print(f"Processing: {email}")
            success = login_to_blomp(email, password)

            if success:
                cur.execute(
                    "UPDATE user_mail_accounts SET last_login_date = NOW() WHERE email = %s",
                    (email,)
                )
                conn.commit()
            else:
                print(f"Skipping {email} due to failure.")

            time.sleep(2)
    finally:
        cur.close()
        conn.close()


@router.get("/trigger-login")
async def trigger_login(background_tasks: BackgroundTasks):
    background_tasks.add_task(run_bulk_login)
    return {"status": "Automation started", "message": "Browser tasks are running in the background."}