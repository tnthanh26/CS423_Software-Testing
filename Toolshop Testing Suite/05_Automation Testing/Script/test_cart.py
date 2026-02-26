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
BASE_URL = "http://localhost:4200/#/"
DATA_FILE = "cart_data.csv"

# BROWSER RUN SETTINGS
BROWSERS = [
    ("chrome", 1, "cart_results_chrome.csv"),
    ("firefox", 2, "cart_results_firefox.csv"),
    ("edge", 3, "cart_results_edge.csv"),
]

# SETUP DRIVER (MULTI-BROWSER)
def setup_driver(browser_choice, browser_name):
    print(f"    [Setup] Launching {browser_name.upper()} (code={browser_choice})...")
    
    win_width = 1200
    win_height = 800
    driver = None

    try:
        if browser_choice == 1:  # Chrome
            options = webdriver.ChromeOptions()
            options.add_argument(f"--window-size={win_width},{win_height}")
            try:
                service = ChromeService(ChromeDriverManager().install())
            except Exception:
                service = ChromeService()
            driver = webdriver.Chrome(service=service, options=options)

        elif browser_choice == 2:  # Firefox
            options = webdriver.FirefoxOptions()
            options.add_argument(f"--width={win_width}")
            options.add_argument(f"--height={win_height}")
            try:
                service = FirefoxService(GeckoDriverManager().install())
            except Exception:
                service = FirefoxService()
            driver = webdriver.Firefox(service=service, options=options)

        elif browser_choice == 3:  # Edge
            options = webdriver.EdgeOptions()
            options.add_argument(f"--window-size={win_width},{win_height}")
            try:
                service = EdgeService(EdgeChromiumDriverManager().install())
            except Exception:
                service = EdgeService()
            driver = webdriver.Edge(service=service, options=options)

        else:
            raise ValueError("Invalid browser_choice")

        driver.set_window_position(0, 0)
        driver.implicitly_wait(5)
        return driver

    except Exception as final_e:
        print(f"\n[CRITICAL] Could not launch browser. Error: {final_e}")
        raise

# HELPER FUNCTIONS
def force_click(driver, element):
    driver.execute_script("arguments[0].click();", element)

def reset_app_state(driver):
    try:
        driver.get(BASE_URL)
        driver.execute_script("window.localStorage.clear();")
        driver.execute_script("window.sessionStorage.clear();")
        driver.delete_all_cookies()
        driver.refresh()
        time.sleep(1)

        try:
            cart_badge = driver.find_element(By.CSS_SELECTOR, "[data-test='cart-quantity']")
            if int(cart_badge.text) > 0:
                nav_cart = driver.find_element(By.CSS_SELECTOR, "[data-test='nav-cart']")
                force_click(driver, nav_cart)
                time.sleep(1)
                deletes = driver.find_elements(By.CSS_SELECTOR, ".fa-remove")
                for btn in deletes:
                    force_click(driver, btn)
                    time.sleep(0.5)
                driver.get(BASE_URL)
        except Exception:
            pass
    except Exception as e:
        print(f"        [Warning] Reset failed: {e}")

def go_home(driver):
    try:
        logo = driver.find_element(By.CSS_SELECTOR, "a.navbar-brand")
        force_click(driver, logo)
        time.sleep(1)
    except Exception:
        driver.get(BASE_URL)

def find_and_click_product(driver, product_name):
    if not product_name:
        return

    if "/product/" in driver.current_url or "checkout" in driver.current_url:
        go_home(driver)

    max_pages = 5
    current_page = 1

    while current_page <= max_pages:
        try:
            xpath = f"//h5[@data-test='product-name' and normalize-space(text())='{product_name}']"
            product_title = driver.find_element(By.XPATH, xpath)
            product_card = product_title.find_element(By.XPATH, "./ancestor::a[@class='card']")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", product_card)
            time.sleep(0.5)
            force_click(driver, product_card)
            time.sleep(1)
            return
        except Exception:
            pass

        try:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(0.5)
            next_link = driver.find_element(By.CSS_SELECTOR, "li.pagination-next a")
            parent_li = next_link.find_element(By.XPATH, "./..")
            if "disabled" in parent_li.get_attribute("class"):
                raise Exception(f"Product '{product_name}' not found (Reached Last Page).")
            force_click(driver, next_link)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(2)
            current_page += 1
        except Exception as e:
            raise Exception(f"Pagination failed looking for '{product_name}': {e}")

def get_cart_total_price(driver):
    try:
        total_element = driver.find_element(By.CSS_SELECTOR, "td[data-test='cart-total']")
        price_text = total_element.text.replace('$', '').replace(',', '').strip()
        return float(price_text)
    except Exception:
        return 0.0

def verify_cart_table_details(driver, product_names_str, expected_qtys_str, check_line_bugs):
    try:
        if "checkout" not in driver.current_url:
            nav_cart = driver.find_element(By.CSS_SELECTOR, "[data-test='nav-cart']")
            force_click(driver, nav_cart)
            WebDriverWait(driver, 3).until(EC.url_contains("checkout"))
            time.sleep(2)

        prods = [p.strip() for p in str(product_names_str).split(',')]
        rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")

        if not rows:
            return False, "Table Empty", 0, []

        found_all = True
        missing_msg = []
        total_found_qty = 0
        line_item_issues = []

        for prod in prods:
            found_row = False
            for row in rows:
                if prod in row.text:
                    found_row = True
                    val = row.find_element(By.CSS_SELECTOR, "input.form-control").get_attribute("value")
                    qty = float(val) if '.' in val else int(val)
                    total_found_qty += qty

                    if check_line_bugs:
                        try:
                            line_price_el = row.find_element(By.CSS_SELECTOR, "td[data-test='line-price']")
                            line_total = float(line_price_el.text.replace('$', '').strip())
                            if line_total == 0.00 and qty > 0:
                                line_item_issues.append(f"Line Total Bug: {prod} shows $0.00")
                        except Exception:
                            pass
                    break
            if not found_row:
                found_all = False
                missing_msg.append(prod)

        if not found_all:
            return False, f"Missing: {', '.join(missing_msg)}", 0, []

        return True, "Found", total_found_qty, line_item_issues

    except Exception as e:
        return False, f"Error: {e}", 0, []

def add_item_and_capture_toast(driver, quantity, product_name):
    found_toast_text = None
    is_error_red = False

    try:
        if "/product/" not in driver.current_url:
            find_and_click_product(driver, product_name)
        else:
            try:
                title = driver.find_element(By.CSS_SELECTOR, "[data-test='product-name']").text
                if product_name not in title:
                    find_and_click_product(driver, product_name)
            except Exception:
                find_and_click_product(driver, product_name)

        qty_input = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='quantity']"))
        )
        qty_input.click()
        qty_input.send_keys(Keys.CONTROL + "a")
        qty_input.send_keys(Keys.DELETE)
        time.sleep(0.2)
        qty_input.send_keys(str(quantity))
        time.sleep(0.5)

        add_btn = driver.find_element(By.CSS_SELECTOR, "[data-test='add-to-cart']")
        force_click(driver, add_btn)

        try:
            toast_container = driver.find_element(By.TAG_NAME, "app-toasts")
            WebDriverWait(driver, 5).until(lambda d: toast_container.text.strip() != "")
            found_toast_text = toast_container.text.strip()

            if "Oeps" in found_toast_text or "wrong" in found_toast_text.lower() or "limit" in found_toast_text.lower():
                is_error_red = True

            if "alert-danger" in toast_container.get_attribute("innerHTML"):
                is_error_red = True

            if "added" not in found_toast_text.lower() and "success" not in found_toast_text.lower():
                is_error_red = True

        except Exception:
            found_toast_text = None

        return found_toast_text, is_error_red

    except Exception as e:
        print(f"        [Error] Add Item Failed: {e}")
        return None, False

def handle_stepper(driver, product_name, operation):
    try:
        if "/product/" not in driver.current_url:
            find_and_click_product(driver, product_name)

        qty_input = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test='quantity']"))
        )

        if operation == "+":
            qty_input.clear()
            qty_input.send_keys("1")
            btn = driver.find_element(By.CSS_SELECTOR, ".fa-plus").find_element(By.XPATH, "./..")
        else:
            qty_input.clear()
            qty_input.send_keys("5")
            btn = driver.find_element(By.CSS_SELECTOR, ".fa-minus").find_element(By.XPATH, "./..")

        force_click(driver, btn)
        time.sleep(0.5)
        return int(qty_input.get_attribute("value"))
    except Exception:
        return 0

# MAIN TEST RUNNER 
def run_tests_for_browser(df, browser_name, browser_choice, output_file):
    print(f"\n================= Running on {browser_name.upper()} =================\n")
    results = []  # will store dict rows for CSV

    driver = setup_driver(browser_choice, browser_name)

    try:
        print(f"Starting execution of {len(df)} test cases on {browser_name}...")

        for index, row in df.iterrows():
            tc_id = row["TC_ID"]
            desc = row["Description"]
            flow = row["Flow_Type"]
            inp = row["Input_Value"]
            prod_name = str(row["Product_Name"]).strip()

            try:
                if "," in str(row["Expected_Qty"]):
                    exp_qtys_str = str(row["Expected_Qty"])
                    exp_qty_total = sum([int(x) for x in exp_qtys_str.split(",")])
                else:
                    exp_qtys_str = str(row["Expected_Qty"])
                    exp_qty_total = int(row["Expected_Qty"])
            except Exception:
                exp_qty_total = 0
                exp_qtys_str = "0"

            exp_err = str(row["Expected_Error"]).strip()

            # PRICE CHECK
            check_price = False
            if exp_err and exp_err.replace(".", "", 1).isdigit():
                check_price = True

            print(f"\n--- Running {tc_id}: {desc} ---")

            reset_app_state(driver)

            actual_price = 0.0
            last_toast_text = None
            is_toast_red = False
            status = "PASS"
            report_messages = []

            if flow == "UIStepper":
                target = 2 if inp == "+" else 4
                end_v = handle_stepper(driver, prod_name, inp)
                if end_v == target:
                    msg = f"Stepper '{inp}' worked"
                    print(f"    [PASS] {msg}")
                    results.append({
                        "TC_ID": tc_id,
                        "Description": desc,
                        "Browser": browser_name,
                        "Status": "PASS",
                        "Details": msg
                    })
                else:
                    msg = f"Stepper '{inp}' stuck/wrong (Exp: {target} vs Act: {end_v})"
                    print(f"    [FAIL] {msg}")
                    results.append({
                        "TC_ID": tc_id,
                        "Description": desc,
                        "Browser": browser_name,
                        "Status": "FAIL",
                        "Details": msg
                    })
                continue

            # Normal flows
            try:
                # INTERACTION
                if flow == "Simple" or flow == "CheckCart":
                    last_toast_text, is_toast_red = add_item_and_capture_toast(driver, inp, prod_name)

                elif flow == "Cumulative":
                    steps = str(inp).split(",")
                    for val in steps:
                        last_toast_text, is_toast_red = add_item_and_capture_toast(driver, val, prod_name)
                        time.sleep(1)

                elif flow == "MultiProd":
                    qtys = str(inp).split(",")
                    prods = prod_name.split(",")
                    for i in range(len(qtys)):
                        go_home(driver)
                        curr_qty = qtys[i] if i < len(qtys) else qtys[0]
                        curr_prod = prods[i] if i < len(prods) else prods[0]
                        last_toast_text, is_toast_red = add_item_and_capture_toast(driver, curr_qty, curr_prod.strip())

                elif flow == "ComplexReset":
                    steps = str(inp).split(",")
                    add_item_and_capture_toast(driver, steps[0], prod_name)

                    nav_cart = driver.find_element(By.CSS_SELECTOR, "[data-test='nav-cart']")
                    force_click(driver, nav_cart)
                    time.sleep(1)

                    try:
                        deletes = driver.find_elements(By.CSS_SELECTOR, ".fa-remove")
                        if deletes:
                            force_click(driver, deletes[0])
                        time.sleep(1)

                        in_table, _, _, _ = verify_cart_table_details(driver, prod_name, "0", False)
                        if in_table:
                            msg = "Delete Button Failed: Item still in cart"
                            print(f"    [FAIL] {msg}")
                            results.append({
                                "TC_ID": tc_id,
                                "Description": desc,
                                "Browser": browser_name,
                                "Status": "FAIL",
                                "Details": msg
                            })
                            continue

                    except Exception:
                        pass

                    go_home(driver)
                    last_toast_text, is_toast_red = add_item_and_capture_toast(driver, steps[2], prod_name)

                elif flow == "Refresh":
                    add_item_and_capture_toast(driver, inp, prod_name)
                    driver.refresh()
                    time.sleep(2)

                # VERIFICATION
                should_check_line_bugs = check_price  # Only check $0.00 bug if price check is relevant

                # 1. TABLE CHECK
                found, msg, qty_val, line_bugs = verify_cart_table_details(
                    driver, prod_name, exp_qtys_str, should_check_line_bugs
                )

                if exp_qty_total == 0:
                    if found and qty_val > 0:
                        status = "FAIL"
                        report_messages.append(
                            f"Invalid Input Added to Cart (Found Qty: {qty_val})"
                        )
                    else:
                        msg_ok = "Passed (Can't find cart as expected)"
                        print(f"    [PASS] {msg_ok}")
                        results.append({
                            "TC_ID": tc_id,
                            "Description": desc,
                            "Browser": browser_name,
                            "Status": "PASS",
                            "Details": msg_ok
                        })
                        continue
                else:
                    if not found:
                        status = "FAIL"
                        report_messages.append(msg)
                    else:
                        if qty_val != exp_qty_total:
                            status = "FAIL"
                            report_messages.append(
                                f"Qty Mismatch (Exp:{exp_qty_total} vs Act:{qty_val})"
                            )
                        else:
                            report_messages.append("Qty updates correctly")

                        if line_bugs:
                            status = "FAIL"
                            report_messages.extend(line_bugs)

                # 2. TOAST CHECK
                if not check_price:
                    if exp_err and not exp_err.replace(".", "", 1).isdigit():
                        if not last_toast_text or exp_err not in str(last_toast_text):
                            status = "FAIL"
                            report_messages.append(
                                f"Expected Error '{exp_err}' NOT found (Got: '{last_toast_text}')"
                            )
                    else:
                        if is_toast_red:
                            status = "FAIL"
                            report_messages.append(
                                f"Bug Detected: Error Toast appeared: '{last_toast_text}'"
                            )

                # 3. GRAND TOTAL CHECK
                if check_price:
                    actual_price = get_cart_total_price(driver)
                    try:
                        exp_price = float(exp_err)
                        if actual_price != exp_price:
                            status = "FAIL"
                            report_messages.append(
                                f"Grand Total Mismatch (Exp:${exp_price} vs Act:${actual_price})"
                            )
                        else:
                            report_messages.append(f"Grand Total Correct (${actual_price})")
                    except Exception:
                        pass

                # Final log for this TC
                if status == "FAIL":
                    msg_full = ", ".join(report_messages)
                    print(f"    [FAIL] {msg_full}")
                else:
                    msg_full = ", ".join(report_messages) if report_messages else "Passed"
                    print(f"    [PASS] {msg_full}")

                results.append({
                    "TC_ID": tc_id,
                    "Description": desc,
                    "Browser": browser_name,
                    "Status": status,
                    "Details": msg_full,
                })

            except Exception as e:
                msg_err = f"Script error: {e}"
                print(f"    [CRITICAL FAIL] {msg_err}")
                results.append({
                    "TC_ID": tc_id,
                    "Description": desc,
                    "Browser": browser_name,
                    "Status": "FAIL",
                    "Details": msg_err,
                })

    finally:
        print(f"\nTest Run Complete on {browser_name}. Closing Browser...")
        driver.quit()

        # Export results for this browser
        df_results = pd.DataFrame(results)
        df_results.to_csv(output_file, index=False, encoding="utf-8")
        print(f"[Info] Results for {browser_name} saved to: {output_file}")

def main():
    try:
        df = pd.read_csv(DATA_FILE)
        df = df.fillna("")
    except Exception:
        print("Error: CSV file not found.")
        return

    for browser_name, browser_choice, output_file in BROWSERS:
        run_tests_for_browser(df, browser_name, browser_choice, output_file)


if __name__ == "__main__":
    main()