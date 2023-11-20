import os, re, time

import requests
from dotenv import load_dotenv, find_dotenv, set_key
from bs4 import BeautifulSoup

from scriptsv2.utils.usable_function import UsableFunc
from scriptsv2.logs.logs_config import CustomLogger

env_path = UsableFunc.paths('kenv')
secrets_dir = UsableFunc.paths('secrets')

logs_dir = os.path.join(os.path.dirname(secrets_dir), 'logs', 'logs')
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)
keyword_tool_logs_dir = os.path.join(logs_dir, 'keyword_tool_scripts')
if not os.path.exists(keyword_tool_logs_dir):
    os.makedirs(keyword_tool_logs_dir)

logging = CustomLogger.log(os.path.join('keyword_tool_scripts', 'atp.log'))

MAX_RETRIES = 5


class ATP:
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            print('Initialized AnswerThePublic')
        logging.info('Initialized AnswerThePublic')
        load_dotenv(env_path)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            'Content-Type': 'application/x-www-form-urlencoded',
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        })
        self.session_id = os.getenv('ANSWERTHEPUBLICS_SESSION_ID')

    def get_keywords(self, keyword):
        print('Getting Keywords from ATP')
        logging.info('Getting Keywords from ATP')
        for i in range(MAX_RETRIES):
            try:
                self.session.cookies.set('_answerthepublic_session', self.session_id)
                page_response = self.session.get('https://answerthepublic.com/fr/s1rqza/member/searches', timeout=5)
                auth_token_match = re.findall(r"authenticity_token\" value=\"(.*?)\"", page_response.text)
                if not auth_token_match:
                    raise Exception(
                        "Auth token not found on member searches page"
                    )
                url = "https://answerthepublic.com/s1rqza/searches"
                self.session.headers.update({
                    "Content-Type": "application/x-www-form-urlencoded",
                })
                data = {
                    'utf8': r'%E2%9C%93',
                    "authenticity_token": auth_token_match[0],
                    "search[keyword]": keyword,
                    "search[region]": "us",
                    "search[language]": "en",
                    "commit": "Search"
                }
                if self.debug:
                    print('Posting keyword search')
                logging.info('Posting keyword search')
                response = self.session.post(url, data=data)
                reports_link_match = re.search(
                    r"https://answerthepublic\.com/s1rqza/reports/(.*?)/edit\?recently_searched=true",
                    response.text
                )
                if not reports_link_match:
                    if self.debug:
                        print("Reports link not found")
                    logging.error("Reports link not found")
                    if i + 1 < MAX_RETRIES:
                        self.login()
                    continue
                reports_link = reports_link_match.group(0)
                if self.debug:
                    print('Getting results link')
                logging.info('Getting results link')
                response = self.session.get(reports_link)
                soup = BeautifulSoup(response.content, 'html.parser')
                keyword_group_elements = soup.find_all(attrs={"data-source-counter": True})
                if not keyword_group_elements:
                    raise Exception(
                        "Error getting results link"
                    )
                code = keyword_group_elements[4].get("data-source-counter")
                keywords_list = []
                keywords = []
                wait_time = 20
                start_time = time.time()
                while not keywords and (time.time()-start_time < wait_time):
                    url = f"https://answerthepublic.com/cpc_data/{code}.json"
                    response = self.session.get(url)
                    if response.status_code != 200:
                        raise Exception(
                            "Error retrieving results"
                        )
                    keyword_groups = response.json()
                    if any([not group['children'] for group in keyword_groups]):
                        time.sleep(1)
                        continue
                    for group in keyword_groups:
                        for child in group['children']:
                            for keyword in child['children']:
                                if keyword['name'] not in keywords:
                                    keywords.append(keyword['name'])
                                    keywords_list.append({
                                        "keyword": keyword['name'],
                                        "search volume": keyword.get('volume', None),
                                        "keyword difficulty": None,
                                        "source": "ATP"
                                    })
                    time.sleep(1)
                if not keywords:
                    raise Exception(
                        "No keywords found"
                    )
                print(f'Successfully retrieved {len(keywords_list)} keywords from ATP')
                logging.info(f'Successfully retrieved {len(keywords_list)} keywords from ATP')

                return keywords_list

            except Exception as e:
                if self.debug:
                    print(f"An error occurred: {str(e)}")
                logging.error(f"An error occurred: {str(e)}")
                if i > 0:
                    self.login()

            if i + 1 < MAX_RETRIES:
                if self.debug:
                    print("Retrying...")
                logging.info("Retrying...")
            else:
                print("Error getting keywords from ATP")
                logging.error("Error getting keywords from ATP")
                return

    def login(self):
        if self.debug:
            print('Logging in')
        logging.info('Logging in')
        self.session.cookies.clear()
        page_response = self.session.get('https://answerthepublic.com/users/sign_in')
        if page_response.status_code != 200:
            raise Exception(
                f"An error occurred logging in\nStatus code: {page_response.status_code}"
            )
        auth_token_match = re.findall(r"authenticity_token\" value=\"(.*?)\"", page_response.text)
        if not auth_token_match[1]:
            raise Exception(
                "Auth token not found on sign in page"
            )
        email = os.getenv('ANSWERTHEPUBLIC_EMAIL')
        password = os.getenv('ANSWERTHEPUBLIC_PASS')
        url = 'https://answerthepublic.com/users/sign_in'
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
        })
        data = {
            'utf8': r'%E2%9C%93',
            "authenticity_token": auth_token_match[1],
            "user[email]": email,
            "user[password]": password,
            "user[remember_me]": "0",
            "commit": "Log in"
        }
        response = self.session.post(url, data=data)
        if response.status_code != 200:
            raise Exception(
                f"An error occurred logging in\nStatus code: {response.status_code}"
            )
        self.session_id = self.session.cookies.get("_answerthepublic_session")
        dotenv_path = find_dotenv(env_path)
        set_key(dotenv_path, 'ANSWERTHEPUBLICS_SESSION_ID', self.session_id)


if __name__ == "__main__":
    print(ATP(debug=True).get_keywords('car rental san antonio'))
