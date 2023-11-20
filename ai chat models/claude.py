import random
import json
import uuid
import re
import os
import time

from curl_cffi import requests
import boto3
import undetected_chromedriver as uc
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

from scriptsv2.logs.logs_config import CustomLogger
from scriptsv2.utils.selenium.error_handler import SeleniumHandler
from scriptsv2.utils.progressbar.progress_icon import ProgressBar
from scriptsv2.utils.usable_function import UsableFunc


logging = CustomLogger.log('claude.log')

DEBUG = False  # keep this false before commits
MAX_RETRIES = 3

load_dotenv(UsableFunc.paths('env'))
os.environ['AWS_ACCESS_KEY_ID'] = os.getenv('BEDROCK_ACCESS_KEY')
os.environ['AWS_SECRET_ACCESS_KEY'] = os.getenv('BEDROCK_SECRET_KEY')

BUCKET_NAME = 'chadix-creds'
FILE_KEY = 'claude_credentials.json'


class ClaudeAI:
    def __init__(self):
        print("\nInitialized ClaudeAI...\n")
        logging.info("\nInitialized ClaudeAI...\n")
        self.s3 = boto3.client('s3')
        response = self.s3.get_object(
            Bucket=BUCKET_NAME,
            Key=FILE_KEY
        )
        file_content_bytes = response['Body'].read()
        file_content_string = file_content_bytes.decode('utf-8')
        self.account_list = json.loads(file_content_string)
        self.account_index = random.randint(0, len(self.account_list)-1)
        self.account_dict = self.account_list[self.account_index]
        self.email = self.account_dict['email']
        print(self.email)
        logging.info(self.email)
        self.gmail_token = self.account_dict['token']
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "*/*",
            "Connection": "keep-alive",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        })
        proxy_url = os.getenv('US_PROXY')
        self.proxy = {
            'http': proxy_url,
            'https': proxy_url
        }
        self.session_id = self.account_dict['session_id']
        self.session.cookies.set('sessionKey', self.session_id)

    def send_prompt(self, prompt):
        pbar = None
        for i in range(MAX_RETRIES):
            try:
                organization_id = self.get_organization_id()
                conversation_id = self.new_conversation(organization_id)
                print("Sending prompt")
                logging.info("Sending prompt")
                url = "https://claude.ai/api/append_message"
                self.session.headers.update({
                    "Content-Type": "application/json"
                })
                payload = {
                    "completion": {
                        "prompt": f"{prompt}",
                        "timezone": "Asia/Kolkata",
                        "model": "claude-2"
                    },
                    "organization_uuid": organization_id,
                    "conversation_uuid": conversation_id,
                    "text": prompt,
                    "attachments": [
                    ]
                }
                response = self.session.post(url, data=json.dumps(payload), impersonate="chrome110", timeout=5*60)
                if DEBUG:
                    print(response.text)
                    print(response.status_code)
                if response.status_code == 200:
                    response_list = ["".join(line.split(": ")[1:]) for line in response.text.splitlines() if
                                     line.strip()]
                    response_dict = [json.loads(line) for line in response_list]
                    response_dict = [line['completion'] for line in response_dict]
                    response_list = []
                    for line in response.text.splitlines():
                        if line.strip():
                            text_dict = "".join(line.split(": ")[1:])
                            text_dict = json.loads(text_dict)
                            text = text_dict['completion']
                            response_list.append(text)
                    response_text = "".join(response_dict).strip()
                    return response_text
                elif response.status_code == 403:
                    if i + 1 < MAX_RETRIES:
                        print('Session ID expired, refreshing')
                        logging.error('Session ID expired, refreshing')
                        self.selenium_login()
                elif response.status_code == 429:
                    if i + 1 < MAX_RETRIES:
                        print("Rate limit error, switching account")
                        logging.error("Rate limit error, switching account")
                        self.__init__()
                else:
                    print(f"An error occurred: {response.text}")
                    logging.error(f"An error occurred: {response.text}")

            except Exception as e:
                print(f"An error occurred: {str(e)}")
                logging.error(f"An error occurred: {str(e)}")
                if str(e) in ['Phone verification required', 'Sending code failed', 'Gmail refresh token expired']:
                    print('Switching account')
                    logging.info('Switching account')
                    self.__init__()

            if i + 1 < MAX_RETRIES:
                print("Retrying...")
                logging.info("Retrying...")
            else:
                return

    def new_conversation(self, organization_id):
        print("Opening new conversation")
        logging.info("Opening new conversation")
        url = f"https://claude.ai/api/organizations/{organization_id}/chat_conversations"
        self.session.headers.update({
            "Content-Type": "application/json"
        })
        payload = {
            "uuid": str(uuid.uuid4()),
            "name": ""
        }
        response = self.session.post(url, data=json.dumps(payload), impersonate="chrome110")
        if DEBUG:
            print(response.text)
            print(response.status_code)
        if response.status_code == 200 or response.status_code == 201:
            conversation_id = response.json()['uuid']
            return conversation_id
        elif response.status_code == 400:
            raise Exception('Invalid uuid')
        elif response.status_code == 403:
            print('Session ID expired, refreshing')
            logging.error('Session ID expired, refreshing')
            self.selenium_login()
        elif response.status_code == 429:
            print("Rate limit error, switching account")
            logging.error("Rate limit error, switching account")
            self.__init__()
        else:
            print(response.status_code)
            print(response.text)
            logging.error(response.status_code)
            logging.error(response.text)

    def get_organization_id(self):
        print("Getting organization id")
        logging.info("Getting organization id")
        url = "https://claude.ai/api/organizations"
        response = self.session.get(url, impersonate="chrome110")
        if DEBUG:
            print(response.text)
            print(response.status_code)
        if response.status_code == 200:
            return response.json()[0]["uuid"]
        elif response.status_code == 403:
            print('Session ID expired, refreshing')
            self.selenium_login()
        elif response.status_code == 429:
            print("Rate limit error, switching account")
            logging.error("Rate limit error, switching account")
            self.__init__()
        else:
            raise Exception(f'Status {response.status_code}')

    def selenium_login(self):
        try:
            self.session.cookies.clear()
            print('Logging in using selenium')
            logging.info('Logging in using selenium')
            chrome_options = uc.ChromeOptions()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
            chrome_options.add_argument("--use-fake-ui-for-media-stream")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option('prefs', {
                "profile.default_content_settings.popups": 0,
                'download.directory_upgrade': True,
                'download.default_directory': "/dev/null",
                "download.prompt_for_download": False,
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False
            })
            # ENABLE THIS TO PRODUCTION
            driver = uc.Chrome(options=chrome_options)
            # ENABLE THIS TO TEST
            # driver = uc.Chrome(executable_path='/usr/bin/chromedriver', options=chrome_options)

            driver.get('https://claude.ai/login')
            old_codes = self.get_gmail_code()
            email_input = SeleniumHandler.locate_until_max_retries(
                driver,
                max_retries=3,
                xpath='//input[@id="email"]',
                wait_element_time=10,
                raise_error=True
            )
            email_input.send_keys(self.email)
            SeleniumHandler.click_until_max_retries(
                driver,
                max_retries=3,
                xpath='//button[@data-testid="continue"]',
                wait_element_time=10,
                raise_error=True
            )
            code_input = SeleniumHandler.locate_until_max_retries(
                driver,
                max_retries=2,
                xpath='//input[@id="code"]',
                wait_element_time=10,
                raise_error=False
            )
            if not code_input:
                raise Exception(
                    'Sending code failed'
                )
            new_codes = self.get_gmail_code()
            start_time = time.time()
            while new_codes == old_codes and (time.time()-start_time < 20):
                new_codes = self.get_gmail_code()
            for code in new_codes:
                if code not in old_codes:
                    code_input.send_keys(code)
                    SeleniumHandler.click_until_max_retries(
                        driver,
                        max_retries=3,
                        xpath='//button[@data-testid="continue"]',
                        wait_element_time=10
                    )
                    success = SeleniumHandler.locate_until_max_retries(
                        driver,
                        max_retries=1,
                        xpath='//*[text()="Welcome back"]',
                        wait_element_time=5,
                        raise_error=False
                    )
                    if not success:
                        verify_phone = SeleniumHandler.locate_until_max_retries(
                            driver,
                            max_retries=1,
                            xpath='//*[text()="Verify Phone"]',
                            wait_element_time=5,
                            raise_error=False
                        )
                        if verify_phone:
                            raise Exception(
                                'Phone verification required'
                            )
                    break
            print(driver.get_cookie('sessionKey').get('value'))
            self.session_id = driver.get_cookie('sessionKey').get('value')
            if not self.session_id:
                raise Exception(
                    "No session token found"
                )
            self.account_dict['session_id'] = self.session_id
            self.account_list[self.account_index] = self.account_dict
            self.s3.put_object(
                Bucket=BUCKET_NAME,
                Key=FILE_KEY,
                Body=json.dumps(self.account_list, indent=2),
                ContentType='application/json'
            )
            driver.quit()
            print('Claude session token is updated successfully')
            logging.info('Claude session token is updated successfully')

        except Exception as e:
            try:
                driver.quit()
            except Exception as error:
                logging.error(error)
            raise e

    def get_gmail_code(self):
        print("\nGetting Gmail Code...")
        logging.info("\nGetting Gmail Code...")
        creds = Credentials.from_authorized_user_info(self.gmail_token)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise Exception(
                    'Gmail refresh token expired'
                )
            self.account_dict['token'] = creds.to_json()
            self.account_list[self.account_index] = self.account_dict
            self.s3.put_object(
                Bucket=BUCKET_NAME,
                Key=FILE_KEY,
                Body=json.dumps(self.account_list, indent=2),
                ContentType='application/json'
            )

        service = build('gmail', 'v1', credentials=creds)
        results = service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            maxResults=10
        ).execute()
        messages = results.get('messages', [])
        codes = []
        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
            # Parse the email content
            payload = msg['payload']
            headers = payload['headers']
            sender = [header['value'] for header in headers if header['name'] == 'From'][0].split("<")[
                0].strip()
            if sender == "Anthropic":
                match = re.search(r'\d{6}', msg['snippet'])
                if match:
                    code = match.group()
                    codes.append(code)
                else:
                    print("No code")

        return codes


if __name__ == "__main__":
    result = ClaudeAI().send_prompt("Hi")
    print(result)
