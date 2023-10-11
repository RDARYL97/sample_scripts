import json, os, base64, re, time

from curl_cffi import requests
from dotenv import load_dotenv, set_key, find_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from scriptsv2.utils.usable_function import UsableFunc
from scriptsv2.logs.logs_config import CustomLogger

env_path = UsableFunc.paths('kenv')
secrets_path = UsableFunc.paths('secrets')
dvm_gmail_token_path = UsableFunc.paths('dvm_gmail_token')  # gmail token of Danny Veiga account
dvm_gmail_credentials_path = UsableFunc.paths('dvm_gmail_cred')
GMAIL_SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

logs_dir = os.path.join(os.path.dirname(secrets_path), 'logs', 'logs')
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)
keyword_tool_logs_dir = os.path.join(logs_dir, 'keyword_tool_scripts')
if not os.path.exists(keyword_tool_logs_dir):
    os.makedirs(keyword_tool_logs_dir)

logging = CustomLogger.log(os.path.join('keyword_tool_scripts', 'ahrefs.log'))

MAX_RETRIES = 5


class Ahrefs:
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            print('Initialized Ahrefs')
        logging.info('Initialized Ahrefs')
        load_dotenv(env_path)
        self.session_id = os.getenv('AHREFS_SESSION_ID')
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "*/*",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Content-Type": "application/json; charset=utf-8",
        })

    def get_keywords(self, keyword):
        print('Getting keywords from Ahrefs')
        logging.info('Getting keywords from Ahrefs')
        for i in range(MAX_RETRIES):
            try:
                url = "https://app.ahrefs.com/v4/keIdeas"
                self.session.cookies.set("BSSESSID", self.session_id)
                data = {
                    "limit": 2000,
                    "offset": 0,
                    "sort": {
                        "order": "Desc",
                        "by": "Volume"
                    },
                    "ideasType": "MatchingTermsTermsMatch",
                    "searchEngine": "Google",
                    "country": "us",
                    "seed": [
                        "Keywords",
                        [keyword]
                    ]
                }
                response = self.session.post(url, data=json.dumps(data), impersonate="chrome110")
                if response.status_code == 200:
                    result_dict = response.json()
                    results_list = result_dict[1]['results']
                    keywords_list = []
                    keywords = []
                    for result in results_list:
                        if result['keyword'] not in keywords:
                            keywords.append(result['keyword'])
                            keywords_list.append({
                                "keyword": result['keyword'],
                                "search volume": result.get('volume', None),
                                "keyword difficulty": result.get('difficulty', None),
                                "source": "Ahrefs"
                            })

                    print(f'Successfully retrieved {len(keywords_list)} keywords from Ahrefs')
                    logging.info(f'Successfully retrieved {len(keywords_list)} keywords from Ahrefs')

                    return keywords_list

                elif response.status_code == 401:
                    if self.debug:
                        print("Session ID expired")
                    logging.error("Session ID expired")
                    if i + 1 < MAX_RETRIES:
                        self.login()
                    continue
                else:
                    raise Exception(
                        f"Status: {response.status_code}\nError message: {response.text}"
                    )

            except Exception as e:
                if self.debug:
                    print(f"An error occurred: {str(e)}")
                logging.error(f"An error occurred: {str(e)}")

            if i + 1 < MAX_RETRIES:
                if self.debug:
                    print("Retrying...")
                logging.info("Retrying...")
            else:
                print("Error getting keywords from Ahrefs")
                logging.error("Error getting keywords from Ahrefs")
                return

    def login(self):
        if self.debug:
            print('Logging in')
        logging.info('Logging in')
        self.session.cookies.clear()
        email = os.getenv('AHREFS_EMAIL')
        password = os.getenv('AHREFS_PASS')
        url = "https://auth.ahrefs.com/auth/login"
        data = {
            "remember_me": False,
            "auth": {
                "login": email,
                "password": password
            }
        }
        response = self.session.post(url, data=json.dumps(data), impersonate="chrome110")
        if response.status_code == 200:
            self.session_id = self.session.cookies.get('BSSESSID')
            dotenv_path = find_dotenv(env_path)
            set_key(dotenv_path, 'AHREFS_SESSION_ID', self.session_id)
            if self.debug:
                print("Login successful")
            logging.info("Login successful")
        elif response.status_code == 401:
            if self.debug:
                print('Verification required')
            logging.error('Verification required')
            self.gmail_confirmation()

        else:
            raise Exception(
                f"Status: {response.status_code}\nError message: {response.text}"
            )

    def gmail_confirmation(self):
        if self.debug:
            print('Getting verification link')
        logging.info('Getting verification link')
        verification_response = self.session.get('https://app.ahrefs.com/verification-required', impersonate="chrome110")
        action_id = re.search(r"actionId\":\"(.*?)\"", verification_response.text)
        if not action_id:
            raise Exception(
                "actionId token not found"
            )

        if action_id.group(1):
            self.resend_verification(action_id.group(1))
        else:
            raise Exception(
                "actionId token not found"
            )
        start_time = time.time()
        while time.time() - start_time < 20:
            verification_links = self.get_auth_links()
            if verification_links:
                for link in verification_links:
                    response = self.session.get(link, impersonate="chrome110")
                    if response.status_code == 200:
                        self.session_id = self.session.cookies.get('BSSESSID')
                        dotenv_path = find_dotenv(env_path)
                        set_key(dotenv_path, 'AHREFS_SESSION_ID', self.session_id)
                        if self.debug:
                            print("Login successful")
                        logging.info("Login successful")
                        return

            time.sleep(2)

        raise Exception(
            f"Error getting verification link on gmail"
        )

    def resend_verification(self, token):
        if self.debug:
            print('Resending verification email')
        logging.info('Resending verification email')
        url = "https://app.ahrefs.com/v4/authResendDeviceVerification"
        data = {
            "action_id": token
        }
        self.session.post(url, data=json.dumps(data), impersonate="chrome110")

    def get_auth_links(self):
        if self.debug:
            print('Getting links on gmail')
        logging.info('Getting links on gmail')
        try:
            creds = None
            if os.path.exists(dvm_gmail_token_path):
                creds = Credentials.from_authorized_user_file(dvm_gmail_token_path, GMAIL_SCOPES)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        dvm_gmail_credentials_path, GMAIL_SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(dvm_gmail_token_path, 'w') as token:
                    token.write(creds.to_json())
            service = build('gmail', 'v1', credentials=creds)
            results = service.users().messages().list(
                userId='me',
                labelIds=['INBOX'],
                maxResults=10
            ).execute()
            messages = results.get('messages', [])
            verification_links = []
            for message in messages:
                msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
                payload = msg['payload']
                headers = payload['headers']
                body = payload.get('body')
                sender = [header['value'] for header in headers if header['name'] == 'From'][0].split("<")[
                    0].strip()
                if sender == 'Ahrefs Support':
                    if body:
                        if 'data' in body and body['data']:
                            body_data = body['data']
                            body_text = base64.urlsafe_b64decode(body_data).decode('utf-8')
                        else:
                            body_text = body

                        button_link_match = re.search(r'<a href="https://auth.ahrefs.com/auth/verify/(.*?)"',
                                                      body_text, re.IGNORECASE)
                        if button_link_match:
                            button_link = f"https://auth.ahrefs.com/auth/verify/{button_link_match.group(1)}"
                            verification_links.append(button_link)

            return verification_links

        except Exception:
            raise Exception(
                "Error getting gmail links"
            )


if __name__ == "__main__":
    print(Ahrefs(debug=True).get_keywords('facebook ads for realtors'))

