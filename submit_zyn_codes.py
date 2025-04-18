#!/usr/bin/env python3
"""
submit_zyn_codes.py

Submit Zyn reward codes to your Zyn Rewards account using the web form.
"""
import os
import sys
import argparse
import getpass

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# Optional Selenium-based browser automation
try:
    import time
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.chrome.service import Service as ChromeService
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    HAVE_SELENIUM = True
except ImportError:
    HAVE_SELENIUM = False

def parse_form(session, url):
    """
    Fetch the page at 'url', parse the first <form>, and return
    (action_url, data_dict) with all input name/value pairs.
    """
    resp = session.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    form = soup.find('form')
    if form is None:
        raise RuntimeError(f'No <form> found at {url}')
    action = form.get('action') or url
    action_url = action if '://' in action else urljoin(url, action)
    data = {}
    for inp in form.find_all('input'):
        name = inp.get('name')
        if not name:
            continue
        data[name] = inp.get('value', '')
    return action_url, data

def login(session, login_url, username, password, verbose=False):
    """
    Log in to the account by submitting the login form at login_url.
    """
    action_url, form_data = parse_form(session, login_url)
    # Identify and fill credential fields (supports default and Zyn field names)
    # Username/email field
    if 'username' in form_data:
        form_data['username'] = username
    elif 'email' in form_data:
        form_data['email'] = username
    elif 'Request.Email' in form_data:
        form_data['Request.Email'] = username
    else:
        print('Could not find username/email field in login form.', file=sys.stderr)
        sys.exit(1)
    # Password field
    if 'password' in form_data:
        form_data['password'] = password
    elif 'Request.Password' in form_data:
        form_data['Request.Password'] = password
    else:
        print('Could not find password field in login form.', file=sys.stderr)
        sys.exit(1)
    # Submit login form and follow redirects to landing page
    # Submit login form and follow redirects, include Referer for anti-forgery
    resp = session.post(action_url, data=form_data, allow_redirects=True,
                        headers={'Referer': login_url})
    resp.raise_for_status()
    if login_url in resp.url or 'login' in resp.url.lower():
        print('Warning: login may have failed (still on login page)', file=sys.stderr)
    elif verbose:
        print('Login succeeded, redirected to', resp.url)
    return session

def submit_code(session, submit_url, code, verbose=False):
    """
    Submit a single reward code via the form at submit_url.
    Returns True on likely success, False otherwise.
    """
    action_url, form_data = parse_form(session, submit_url)
    # Inject the code
    if 'code' in form_data:
        form_data['code'] = code
    elif 'reward_code' in form_data:
        form_data['reward_code'] = code
    else:
        # fallback: first empty field
        for k, v in form_data.items():
            if v == '':
                form_data[k] = code
                break
        else:
            form_data['code'] = code
    # Submit reward code form and follow redirects to confirmation page
    # Submit reward code form and follow redirects, include Referer for anti-forgery
    resp = session.post(action_url, data=form_data, allow_redirects=True,
                        headers={'Referer': submit_url})
    resp.raise_for_status()
    text = resp.text.lower()
    if 'thank' in text or 'success' in text:
        if verbose:
            print(f'Code {code} submitted successfully')
        return True
    else:
        if verbose:
            print(f'Code {code} submission status unclear')
        return False
 
def submit_codes_browser(login_url, submit_url, codes, username, password, dry_run=False, verbose=False):
    """
    Submit reward codes using Selenium browser automation.
    """
    # Configure headless Chrome WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options
    )
    try:
        # Login sequence
        driver.get(login_url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'form'))
        )
        # Fill username/email
        for field in ('username', 'email', 'Request.Email'):
            try:
                elem = driver.find_element(By.NAME, field)
                elem.clear()
                elem.send_keys(username)
                if verbose:
                    print(f'Filled username field: {field}')
                break
            except Exception:
                continue
        else:
            print('Could not find username/email field on login page', file=sys.stderr)
            driver.quit()
            sys.exit(1)
        # Fill password
        for field in ('password', 'Request.Password'):
            try:
                pwd = driver.find_element(By.NAME, field)
                pwd.clear()
                pwd.send_keys(password)
                if verbose:
                    print(f'Filled password field: {field}')
                break
            except Exception:
                continue
        else:
            print('Could not find password field on login page', file=sys.stderr)
            driver.quit()
            sys.exit(1)
        # Submit login form
        pwd.send_keys(Keys.RETURN)
        WebDriverWait(driver, 10).until(lambda d: d.current_url != login_url)
        if verbose:
            print('Login succeeded, current URL:', driver.current_url)
        # Submit each code
        if dry_run:
            print(f'[DRY-RUN] Would submit {len(codes)} codes via browser')
        else:
            print(f'Submitting {len(codes)} codes via browser...')
        for code in codes:
            if dry_run:
                print('[DRY-RUN] Would submit:', code)
                continue
            driver.get(submit_url)
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'form'))
            )
            # Fill code field
            for field in ('code', 'reward_code'):
                try:
                    inp = driver.find_element(By.NAME, field)
                    inp.clear()
                    inp.send_keys(code)
                    if verbose:
                        print(f'Filled code field: {field} with {code}')
                    break
                except Exception:
                    continue
            else:
                # Fallback: first text input
                try:
                    inp = driver.find_element(By.XPATH, "//input[@type='text']")
                    inp.clear()
                    inp.send_keys(code)
                    if verbose:
                        print(f'Filled fallback text input with {code}')
                except Exception as e:
                    print(f'Could not find code input: {e}', file=sys.stderr)
                    continue
            # Submit code form
            inp.send_keys(Keys.RETURN)
            time.sleep(2)
            page = driver.page_source.lower()
            if 'thank' in page or 'success' in page:
                print(f'{code}: OK')
            else:
                print(f'{code}: FAIL or unclear')
    except Exception as e:
        print(f'Browser automation error: {e}', file=sys.stderr)
        sys.exit(1)
    finally:
        driver.quit()

def main():
    parser = argparse.ArgumentParser(description='Submit Zyn reward codes to your account')
    parser.add_argument(
        '--login-url',
        default='https://us.zyn.com/login/',
        help='URL of the login page (default: %(default)s)'
    )
    parser.add_argument(
        '--submit-url',
        default='https://us.zyn.com/ZYNRewards/',
        help='URL of the code submission page (default: %(default)s)'
    )
    parser.add_argument('--codes-file', default='codes.txt', help='File containing codes to submit (one per line)')
    parser.add_argument('--username', help='Account username/email (or set ZYN_USERNAME env var)')
    parser.add_argument('--password', help='Account password (or set ZYN_PASSWORD env var)')
    parser.add_argument('--dry-run', action='store_true', help="Don't actually submit, just print codes")
    parser.add_argument('--browser', action='store_true', help='Use Selenium browser automation for submission')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    args = parser.parse_args()

    username = args.username or os.environ.get('ZYN_USERNAME')
    password = args.password or os.environ.get('ZYN_PASSWORD')
    if not username:
        username = input('Username/email: ')
    if not password:
        password = getpass.getpass('Password: ')

    if not os.path.isfile(args.codes_file):
        print(f'Codes file {args.codes_file} not found', file=sys.stderr)
        sys.exit(1)
    with open(args.codes_file) as f:
        codes = [line.strip() for line in f if line.strip()]
    if not codes:
        print('No codes found in codes file', file=sys.stderr)
        sys.exit(1)

    # Decide on submission method: HTTP requests or Selenium browser
    if args.browser:
        if not HAVE_SELENIUM:
            print('Error: Selenium or webdriver-manager not installed. Please install requirements.', file=sys.stderr)
            sys.exit(1)
        # Browser automation submission
        submit_codes_browser(
            login_url=args.login_url,
            submit_url=args.submit_url,
            codes=codes,
            username=username,
            password=password,
            dry_run=args.dry_run,
            verbose=args.verbose
        )
    else:
        # HTTP-based submission
        session = requests.Session()
        login(session, args.login_url, username, password, verbose=args.verbose)
        print(f'Submitting {len(codes)} codes...')
        for code in codes:
            if args.dry_run:
                print('[DRY-RUN] Would submit:', code)
                continue
            try:
                ok = submit_code(session, args.submit_url, code, verbose=args.verbose)
                print(f'{code}: {"OK" if ok else "FAIL"}')
            except Exception as e:
                print(f'{code}: ERROR ({e})')

if __name__ == '__main__':
    main()