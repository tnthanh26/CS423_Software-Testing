import re
import time
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

# Drivers
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.firefox.service import Service as FirefoxService
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.edge.service import Service as EdgeService
from webdriver_manager.microsoft import EdgeChromiumDriverManager

# CONFIGURATION
LOGIN_URL = "http://localhost:4200/#/auth/login"
BASE_URL = "http://localhost:4200/#/"
DATA_FILE = "product_data.csv"

# Admin Credentials
ADMIN_EMAIL = "admin@practicesoftwaretesting.com"
ADMIN_PASS = "welcome01"

# TEXT HELPERS
def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)          # remove punctuation
    s = re.sub(r"\b(the|field)\b", " ", s)  # drop filler words
    s = re.sub(r"\s+", " ", s).strip()
    return s

def page_contains_text(driver, text: str) -> bool:
    try:
        return normalize_text(text) in normalize_text(driver.page_source)
    except Exception:
        return False

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

def admin_login(driver):
    try:
        driver.get(LOGIN_URL)
        time.sleep(1)

        email_in = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='email']"))
        )
        pass_in = driver.find_element(By.CSS_SELECTOR, "[data-test='password']")

        email_in.send_keys(ADMIN_EMAIL)
        pass_in.send_keys(ADMIN_PASS)

        driver.find_element(By.CSS_SELECTOR, "[data-test='login-submit']").click()

        # Wait until we are out of /auth and into a logged-in page
        WebDriverWait(driver, 10).until(
            lambda d: ("auth/login" not in d.current_url)
            and ("auth" not in d.current_url)
        )
        print("    [Info] Admin Login Successful")

    except Exception as e:
        print(f"    [Error] Login Failed: {e}")
        raise

def go_to_products_page(driver):
    try:
        driver.get(BASE_URL + "admin/products")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "[data-test='product-add']")
            )
        )
    except Exception:
        print("    [Error] Could not reach Products Page")

def smart_input(driver, field_name, value):
    # Normalize CSV value
    if value is None:
        return

    raw_str = str(value)

    # Check for "skip" condition 
    if raw_str == "" or raw_str.lower() == "nan":
        return

    # Determine action: Clear only OR Clear & Type
    to_type = ""
    if raw_str == " ":
        # User wants to clear the field 
        to_type = ""
    else:
        # User wants to type a specific value
        to_type = raw_str.strip()

    try:
        # 1. Locate element by data-test first, then by id
        try:
            el = driver.find_element(By.CSS_SELECTOR, f"[data-test='{field_name}']")
        except Exception:
            el = driver.find_element(By.ID, field_name)

        # Scroll into view
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
        except Exception:
            pass
        time.sleep(0.05)

        # click into the field
        try:
            el.click()
        except Exception:
            pass
        time.sleep(0.05)

        # a) standard clear()
        try:
            el.clear()
        except Exception:
            pass

        # b) CTRL+A + DELETE as backup
        try:
            el.send_keys(Keys.CONTROL, "a")
            el.send_keys(Keys.DELETE)
        except Exception:
            pass

        # c) Backspace Loop
        try:
            current_val = el.get_attribute("value")
            if current_val:
                for _ in range(len(str(current_val)) + 1):
                    el.send_keys(Keys.BACK_SPACE)
        except Exception:
            pass

        # d) JS clear + fire events so Angular/reactive form sees it
        try:
            driver.execute_script(
                """
                const el = arguments[0];
                el.value = '';
                el.dispatchEvent(new Event('input',  { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                """,
                el,
            )
        except Exception:
            pass

        time.sleep(0.1)

        # 3. Type the new value
        if to_type != "":
            el.send_keys(to_type)
            time.sleep(0.1)

            # Extra JS set fallback if typing failed
            current_val = el.get_attribute("value")
            if current_val != to_type:
                driver.execute_script(
                    "arguments[0].value = arguments[1];"
                    "arguments[0].dispatchEvent(new Event('input', { bubbles: true }));",
                    el,
                    to_type,
                )

    except Exception as e:
        print(f"    [WARN] smart_input failed for '{field_name}': {e}")

def smart_select(driver, field_name, value):
    if value is None:
        return

    value_str = str(value).strip()
    if not value_str or value_str.lower() == "nan":
        return

    try:
        # Locate the <select>
        try:
            el = driver.find_element(By.CSS_SELECTOR, f"[data-test='{field_name}']")
        except Exception:
            el = driver.find_element(By.ID, field_name)

        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)

        # Convert numeric ID
        try:
            select_value = str(int(float(value_str)))
        except ValueError:
            select_value = value_str

        # Fast JS assignment
        driver.execute_script(
            """
            const sel = arguments[0];
            const val = arguments[1];
            sel.value = val;
            sel.dispatchEvent(new Event('change', { bubbles: true }));
            """,
            el,
            select_value,
        )

    except Exception:
        pass

def smart_check(driver, field_name, should_check):
    if not should_check:
        return

    try:
        try:
            el = driver.find_element(By.CSS_SELECTOR, f"[data-test='{field_name}']")
        except Exception:
            el = driver.find_element(By.ID, field_name)

        if not el.is_selected():
            force_click(driver, el)
    except Exception:
        pass

def capture_toasts(driver):
    toasts_found = []
    has_success = False
    has_error = False

    selector = (
        ".toast, .toast-message, .toast-container .toast, "
        ".alert, [role='alert']"
    )

    try:
        # Wait up to 3 seconds for ANY toast/alert to show up
        try:
            WebDriverWait(driver, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
        except TimeoutException:
            # none visible within timeout
            pass

        elems = driver.find_elements(By.CSS_SELECTOR, selector)

    except Exception:
        return toasts_found, has_success, has_error

    for t in elems:
        try:
            if not t.is_displayed():
                continue
            text = t.text.strip()
            if not text:
                continue

            toasts_found.append(text)

            classes = (t.get_attribute("class") or "").lower()
            txt = text.lower()

            # Success detection
            if (
                "success" in classes
                or "alert-success" in classes
                or "bg-success" in classes
                or "product saved" in txt
            ):
                has_success = True

            # Error/validation detection
            if (
                "danger" in classes
                or "alert-danger" in classes
                or "error" in classes
                or "invalid" in classes
                or any(k in txt for k in ["required", "must be", "wrong", "invalid"])
            ):
                has_error = True

        except StaleElementReferenceException:
            continue
        except Exception:
            continue

    return toasts_found, has_success, has_error

# MAIN TEST LOOP
def run_admin_tests():
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
            admin_login(driver)
            print(f"Starting execution of {len(df)} test cases on {browser.upper()}...")

            for index, row in df.iterrows():
                tc_id = row["TC_ID"]
                desc = row["Description"]
                flow = row["Flow_Type"]
                target_prod = str(row["Target_Product"]).strip()
                exp_err = str(row["Expected_Error"]).strip()

                print(f"\n--- {browser.upper()} | {tc_id}: {desc} ---")

                go_to_products_page(driver)

                status = "PASS"
                fail_reason = ""
                pass_message = ""
                joined_toasts = ""
                actual_error_seen = ""

                try:
                    # HANDLE FLOWS
                    if flow == "Add":
                        add_btn = driver.find_element(
                            By.CSS_SELECTOR, "[data-test='product-add']"
                        )
                        force_click(driver, add_btn)

                        # Wait for the Name field to appear
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located(
                                (By.CSS_SELECTOR, "[data-test='name']")
                            )
                        )

                        # Fill Text Fields
                        smart_input(driver, "name", row["Name"])
                        smart_input(driver, "price", row["Price"])
                        smart_input(driver, "stock", row["Stock"])
                        smart_input(driver, "description", row["Description_Input"])

                        # Fill Dropdowns
                        smart_select(driver, "brand_id", row["Brand"])
                        smart_select(driver, "category_id", row["Category"])
                        smart_select(driver, "product_image_id", row["Image"])
                        smart_select(driver, "co2_rating", row["CO2"])

                        driver.execute_script(
                            "window.scrollTo(0, document.body.scrollHeight);"
                        )
                        time.sleep(0.5)

                        # Fill Checkboxes
                        smart_check(driver, "is_location_offer", row["Check_Location"])
                        smart_check(driver, "is_rental", row["Check_Rental"])

                        save_btn = driver.find_element(
                            By.CSS_SELECTOR, "[data-test='product-submit']"
                        )
                        force_click(driver, save_btn)

                    elif flow == "Edit":
                        try:
                            # Always start from the product list page
                            go_to_products_page(driver)

                            # Row whose 2nd cell (Name column) matches target_prod exactly
                            row_xpath = (
                                "//app-products-list//table//tbody"
                                f"//tr[td[2][normalize-space(.)='{target_prod}']]"
                            )

                            row_el = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.XPATH, row_xpath))
                            )

                            # Find the Edit button inside that row
                            try:
                                edit_btn = row_el.find_element(
                                    By.CSS_SELECTOR, "a[data-test^='product-edit']"
                                )
                            except NoSuchElementException:
                                edit_btn = row_el.find_element(
                                    By.XPATH, ".//a[normalize-space(text())='Edit']"
                                )

                            driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'center'});",
                                edit_btn,
                            )
                            time.sleep(0.3)
                            force_click(driver, edit_btn)
                            time.sleep(0.5)

                            # Now we are on the edit form – update fields if provided
                            if row["Name"]:
                                smart_input(driver, "name", row["Name"])
                            if row["Price"]:
                                smart_input(driver, "price", row["Price"])
                            if str(row["Stock"]).strip() != "":
                                smart_input(driver, "stock", row["Stock"])
                            if row["Description_Input"]:
                                smart_input(driver, "description", row["Description_Input"])

                            save_btn = driver.find_element(
                                By.CSS_SELECTOR, "[data-test='product-submit']"
                            )
                            driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'center'});",
                                save_btn,
                            )
                            time.sleep(0.3)
                            force_click(driver, save_btn)

                        except Exception as e:
                            msg = f"Could not find product '{target_prod}' to Edit: {e}"
                            print(f"    [FAIL] {msg}")
                            status = "SCRIPT_ERROR"
                            fail_reason = msg

                    # VERIFICATION
                    max_attempts = 3
                    attempt_delay = 0.7  # seconds

                    toasts = []
                    has_success = False
                    has_error = False

                    for attempt in range(max_attempts):
                        toasts, has_success, has_error = capture_toasts(driver)
                        joined_toasts = " | ".join(toasts)

                        norm_expected = normalize_text(exp_err)
                        norm_page = normalize_text(driver.page_source)
                        norm_toasts_list = [normalize_text(t) for t in toasts]

                        match_in_toasts = bool(
                            exp_err
                            and norm_expected
                            and any(norm_expected in nt for nt in norm_toasts_list)
                        )
                        match_in_page = bool(
                            exp_err and norm_expected and norm_expected in norm_page
                        )

                        # If we expect an error and we've seen it → stop retrying.
                        if exp_err and (match_in_toasts or match_in_page):
                            break

                        # If we don't expect an error and we already have success or error flags, no need to wait more.
                        if not exp_err and (has_success or has_error):
                            break

                        if attempt < max_attempts - 1:
                            time.sleep(attempt_delay)

                    # After retries, decide PASS/FAIL
                    if status != "SCRIPT_ERROR":  # only evaluate if earlier logic didn't blow up
                        if exp_err:
                            norm_expected = normalize_text(exp_err)
                            norm_page = normalize_text(driver.page_source)
                            norm_toasts_list = [normalize_text(t) for t in toasts]

                            match_in_toasts = bool(
                                norm_expected
                                and any(norm_expected in nt for nt in norm_toasts_list)
                            )
                            match_in_page = bool(
                                norm_expected and norm_expected in norm_page
                            )

                            if match_in_toasts or match_in_page:
                                # Only show the toast(s) that match expected error, if any
                                if match_in_toasts:
                                    matched_toasts = [
                                        t
                                        for t, nt in zip(toasts, norm_toasts_list)
                                        if norm_expected in nt
                                    ]
                                    shown = " | ".join(matched_toasts)
                                else:
                                    # Inline-only error; show expected text as what we looked for
                                    shown = exp_err

                                actual_error_seen = shown
                                pass_message = (
                                    f"[PASS] Expected error present. Seen: {shown}"
                                )
                            else:
                                status = "FAIL"
                                fail_reason = (
                                    f"Expected Error '{exp_err}' NOT found "
                                    f"(Got: '{joined_toasts or 'NO TOASTS/ERROR TEXT FOUND'}')"
                                )
                        else:
                            # We expect success
                            if has_success:
                                if has_error:
                                    pass_message = (
                                        f"[PASS] Success + Error both shown: {joined_toasts}"
                                    )
                                else:
                                    pass_message = (
                                        f"[PASS] Success: {joined_toasts or 'No toast text'}"
                                    )
                            elif has_error:
                                status = "FAIL"
                                fail_reason = (
                                    f"Unexpected Error: '{joined_toasts or 'NO TEXT'}'"
                                )
                            else:
                                pass_message = "[PASS] No toasts shown (silent success)."

                    # Print final line for this test case
                    if status == "FAIL":
                        print(f"    [FAIL] {fail_reason}")
                    elif status == "SCRIPT_ERROR":
                        print(f"    [SCRIPT_ERROR] {fail_reason}")
                    else:
                        print(f"    {pass_message}")

                    # RESET PAGE FOR NEXT TEST CASE
                    try:
                        if flow == "Add":
                            # Prefer Back link if present
                            try:
                                back_link = driver.find_element(
                                    By.CSS_SELECTOR, "[data-test='back']"
                                )
                                back_link.click()
                            except Exception:
                                driver.get(BASE_URL + "admin/products")

                            WebDriverWait(driver, 5).until(
                                EC.presence_of_element_located(
                                    (By.CSS_SELECTOR, "[data-test='product-add']")
                                )
                            )
                        else:
                            # For Edit, ensure we're on the list
                            go_to_products_page(driver)
                    except Exception as nav_e:
                        print(f"    [WARN] Could not reset page cleanly: {nav_e}")
                        driver.get(BASE_URL + "admin/products")

                except Exception as e:
                    print(f"    [CRITICAL FAIL] Script error: {e}")
                    status = "SCRIPT_ERROR"
                    fail_reason = str(e)
                    driver.refresh()
                    go_to_products_page(driver)

                # Record result row
                results.append(
                    {
                        "TC_ID": tc_id,
                        "Description": desc,
                        "Browser": browser,
                        "Flow_Type": flow,
                        "Status": status,
                        "Expected_Error": exp_err,
                        "Actual_Error_Seen": actual_error_seen,
                        "Toasts": joined_toasts,
                        "Details": fail_reason if status != "PASS" else pass_message,
                    }
                )

        finally:
            print(f"\nTest Run Complete for {browser.upper()}. Closing Browser...")
            driver.quit()

            # Save CSV report for this browser
            out_file = f"results_product_{browser}.csv"
            pd.DataFrame(results).to_csv(out_file, index=False)
            print(f"[INFO] Results saved to {out_file}")

if __name__ == "__main__":
    run_admin_tests()