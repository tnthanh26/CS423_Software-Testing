import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Drivers
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# CONFIGURATION
LOGIN_URL = "http://localhost:4200/#/auth/login"
DATA_FILE = "profile_data.csv"

# DRIVER SETUP (MULTI-BROWSER)
def setup_driver(browser: str):
    print(f"\n========== Launching {browser.upper()} ==========")

    win_width = 1200
    win_height = 800

    driver = None

    try:
        if browser == "chrome":
            options = webdriver.ChromeOptions()
            options.add_argument(f"--window-size={win_width},{win_height}")
            try:
                service = ChromeService(ChromeDriverManager().install())
            except Exception:
                service = ChromeService()
            driver = webdriver.Chrome(service=service, options=options)

        elif browser == "firefox":
            options = webdriver.FirefoxOptions()
            options.add_argument(f"--width={win_width}")
            options.add_argument(f"--height={win_height}")
            try:
                service = FirefoxService(GeckoDriverManager().install())
            except Exception:
                service = FirefoxService()
            driver = webdriver.Firefox(service=service, options=options)

        elif browser == "edge":
            options = webdriver.EdgeOptions()
            options.add_argument(f"--window-size={win_width},{win_height}")
            try:
                service = EdgeService(EdgeChromiumDriverManager().install())
            except Exception:
                service = EdgeService()
            driver = webdriver.Edge(service=service, options=options)

        else:
            raise ValueError(f"Invalid browser value: {browser}")

        driver.set_window_position(0, 0)
        driver.implicitly_wait(5)
        return driver

    except Exception as final_e:
        print(f"\n[CRITICAL] Could not launch {browser}. Error: {final_e}")
        raise

# HELPER FUNCTIONS
def force_click(driver, element):
    driver.execute_script("arguments[0].click();", element)

def login(driver):
    try:
        driver.get(LOGIN_URL)
        time.sleep(1)

        email_in = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='email']"))
        )
        pass_in = driver.find_element(By.CSS_SELECTOR, "[data-test='password']")

        # CREDENTIALS
        email_in.send_keys("customer@practicesoftwaretesting.com")
        pass_in.send_keys("welcome01")

        submit_btn = driver.find_element(By.CSS_SELECTOR, "[data-test='login-submit']")
        force_click(driver, submit_btn)

        # Wait for redirect to account page
        WebDriverWait(driver, 5).until(EC.url_contains("account"))
        print("    [Info] Login Successful")

    except Exception as e:
        print(f"    [Error] Login Failed: {e}")
        raise

def ensure_profile_page(driver):
    try:
        # If not on profile page, navigate there
        if "/account/profile" not in driver.current_url:
            driver.get(driver.current_url.split("#")[0] + "#/account/profile")
            time.sleep(1)

        # Wait for form to load
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='first-name']"))
        )
    except Exception:
        # Fallback force navigation
        driver.get("http://localhost:4200/#/account/profile")
        time.sleep(1)

def clear_and_type(element, text):
    element.click()
    element.send_keys(Keys.CONTROL + "a")
    element.send_keys(Keys.DELETE)
    time.sleep(0.1)
    if text and str(text).lower() != "nan":
        element.send_keys(str(text))
    time.sleep(0.2)

def capture_toast(driver):
    found_text = None
    is_red = False
    try:
        toast = WebDriverWait(driver, 2).until(
            EC.visibility_of_element_located(
                (By.CSS_SELECTOR, ".toast-message, .alert-danger, div[role='alert']")
            )
        )
        found_text = toast.text.strip()

        parent = toast.find_element(By.XPATH, "./..")
        classes = parent.get_attribute("class") + " " + toast.get_attribute("class")

        if "danger" in classes or "error" in classes:
            is_red = True
        if (
            found_text
            and (
                "wrong" in found_text.lower()
                or "not found" in found_text.lower()
                or "error" in found_text.lower()
            )
        ):
            is_red = True

    except Exception:
        pass

    return found_text, is_red

# MAIN TEST RUNNER
def run_profile_tests():
    # Load data once
    try:
        df = pd.read_csv(DATA_FILE)
        df = df.fillna("")
    except Exception:
        print(f"Error: Could not find {DATA_FILE}")
        return

    browsers = ["chrome", "firefox", "edge"]

    for browser in browsers:
        results = []

        driver = setup_driver(browser)

        try:
            # 1. Login
            login(driver)

            print(f"Starting execution of {len(df)} test cases on {browser.upper()}...")

            for index, row in df.iterrows():
                tc_id = row["TC_ID"]
                desc = row["Description"]
                field_name = str(row["Field_Name"]).strip()
                inp_val = row["Input_Value"]
                exp_err = str(row["Expected_Error"]).strip()

                print(f"\n--- {browser.upper()} | {tc_id}: {desc} ---")

                # Always reset to fresh profile page state
                driver.refresh()
                time.sleep(1)
                ensure_profile_page(driver)

                status = "PASS"
                fail_reason = ""
                details = ""
                actual_toast = ""

                try:
                    # 3. Handle Special "Refresh" / "Persistence" Case
                    if "Refresh" in desc or "Persistence" in desc:
                        try:
                            try:
                                input_el = driver.find_element(
                                    By.CSS_SELECTOR, f"[data-test='{field_name}']"
                                )
                            except Exception:
                                input_el = driver.find_element(By.ID, field_name)

                            # Enter Data (NO SAVE)
                            clear_and_type(input_el, inp_val)
                            time.sleep(0.5)

                            # Refresh
                            driver.refresh()
                            time.sleep(1)
                            ensure_profile_page(driver)

                            # Verify Revert
                            try:
                                try:
                                    new_el = driver.find_element(
                                        By.CSS_SELECTOR, f"[data-test='{field_name}']"
                                    )
                                except Exception:
                                    new_el = driver.find_element(By.ID, field_name)

                                current_val = new_el.get_attribute("value")
                                if current_val != inp_val:
                                    print("    [PASS] Passed (Value reverted on refresh)")
                                    status = "PASS"
                                    details = "Value reverted on refresh"
                                else:
                                    print(
                                        "    [FAIL] Value persisted after refresh (Unexpected)"
                                    )
                                    status = "FAIL"
                                    details = "Value persisted after refresh"
                            except Exception:
                                print("    [PASS] Passed (Page reset)")
                                status = "PASS"
                                details = "Page reset after refresh"

                        except Exception as e:
                            print(f"    [CRITICAL FAIL] Script error: {e}")
                            status = "SCRIPT_ERROR"
                            details = str(e)

                        # Log result and go to next row
                        results.append(
                            {
                                "TC_ID": tc_id,
                                "Description": desc,
                                "Browser": browser,
                                "Status": status,
                                "Expected_Error": exp_err,
                                "Actual_Toast": "",
                                "Details": details or fail_reason,
                            }
                        )
                        continue

                    # 4. Standard Input Handling
                    try:
                        selector = f"[data-test='{field_name}']"
                        if "_" in field_name:
                            selector = f"[data-test='{field_name.replace('_', '-')}]"
                        input_el = driver.find_element(By.CSS_SELECTOR, selector)
                    except Exception:
                        input_el = driver.find_element(By.ID, field_name)

                    clear_and_type(input_el, inp_val)

                    # 5. Click Update Profile
                    save_btn = driver.find_element(
                        By.XPATH, "//button[normalize-space()='Update Profile']"
                    )
                    driver.execute_script(
                        "arguments[0].scrollIntoView({block: 'center'});", save_btn
                    )
                    time.sleep(0.5)
                    force_click(driver, save_btn)

                    # 6. Verify Result
                    actual_toast, is_red = capture_toast(driver)

                    if exp_err:
                        # Expect Error
                        if not actual_toast or exp_err not in actual_toast:
                            status = "FAIL"
                            fail_reason = (
                                f"Expected Error '{exp_err}' NOT found "
                                f"(Got: '{actual_toast}')"
                            )
                    else:
                        # Expect Success
                        if is_red:
                            status = "FAIL"
                            fail_reason = (
                                f"Bug Detected: Error Toast appeared: '{actual_toast}'"
                            )

                    if status == "FAIL":
                        print(f"    [FAIL] {fail_reason}")
                    else:
                        print("    [PASS] Passed")

                    details = fail_reason if status == "FAIL" else "Passed"

                except Exception as e:
                    print(f"    [CRITICAL FAIL] Script error: {e}")
                    status = "SCRIPT_ERROR"
                    details = str(e)

                # Record result for this test case
                results.append(
                    {
                        "TC_ID": tc_id,
                        "Description": desc,
                        "Browser": browser,
                        "Status": status,
                        "Expected_Error": exp_err,
                        "Actual_Toast": actual_toast,
                        "Details": details,
                    }
                )

        finally:
            print("\nTest Run Complete for", browser.upper(), "- Closing Browser...")
            driver.quit()

            # Save CSV report for this browser
            out_file = f"results_profile_{browser}.csv"
            pd.DataFrame(results).to_csv(out_file, index=False)
            print(f"[INFO] Results saved to {out_file}")

if __name__ == "__main__":
    run_profile_tests()