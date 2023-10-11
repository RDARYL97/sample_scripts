import os, re, json, time

import requests
from dotenv import load_dotenv, find_dotenv, set_key

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

logging = CustomLogger.log(os.path.join('keyword_tool_scripts', 'writerzen.log'))

MAX_RETRIES = 5


class WriterZen:
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            print('Initialized WriterZen')
        logging.info('Initialized WriterZen')
        load_dotenv(env_path)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        })
        self.session_id = os.getenv('WRITERZEN_SESSION_ID')
        self.xsrf_token = os.getenv('WRITERZEN_XSRF_TOKEN')

    def get_keywords(self, keyword):
        print('Getting Keywords from WriterZen')
        logging.info('Getting Keywords from WriterZen')
        for i in range(MAX_RETRIES):
            try:
                url = "https://app.writerzen.net/api/services/keyword-explorer/v2/task"
                x_xsrf_token = f'{self.xsrf_token[:-3]}='
                self.session.headers.update({
                    "Content-Type": "application/json",
                    "X-Xsrf-Token": x_xsrf_token,
                })
                self.session.cookies.set('writerzen_session', self.session_id)
                self.session.cookies.set('XSRF-TOKEN', self.xsrf_token)
                data = {
                    "input": keyword,
                    "type": "keyword",
                    "language_id": 1000,
                    "location_id": 2840
                }
                response = self.session.post(url, data=json.dumps(data))
                if response.status_code != 200:
                    if self.debug:
                        print("Session token expired")
                    logging.error("Session token expired")
                    if i + 1 < MAX_RETRIES:
                        self.session_id, self.xsrf_token = self.login()
                    continue
                elif response.json()['status'] != 200:
                    raise Exception(
                        "Error getting keywords, status not 200"
                    )
                task_id = response.json()['data']['id']
                url = "https://app.writerzen.net/api/services/keyword-explorer/v2/task/get-data"
                params = {
                    "id": task_id
                }
                task_status = 0
                start_time = time.time()
                if self.debug:
                    print('Getting Results')
                logging.info('Getting Results')
                while task_status == 0 and (time.time() - start_time < 20):
                    response = self.session.get(url, params=params)
                    if response.json()['status'] != 200:
                        raise Exception(
                            "Error getting keywords, status not 200"
                        )
                    task_status = response.json()['data']['status']
                    time.sleep(0.5)
                keywords_data = response.json()['data']['ideas']
                keywords = []
                keywords_list = []
                for result in keywords_data:
                    if result['keyword'] not in keywords:
                        keywords.append(result['keyword'])
                        keywords_list.append({
                            "keyword": result['keyword'],
                            "search volume": result.get('search_volume', None),
                            "keyword difficulty": result.get('competition', None),
                            "source": "WriterZen"
                        })

                print(f'Successfully retrieved {len(keywords_list)} keywords from WriterZen')
                logging.info(f'Successfully retrieved {len(keywords_list)} keywords from WriterZen')

                return keywords_list

            except Exception as e:
                if self.debug:
                    print(f"An error occurred: {str(e)}")
                logging.error(f"An error occurred: {str(e)}")

            if i + 1 < MAX_RETRIES:
                if self.debug:
                    print("Retrying...")
                logging.info("Retrying...")
            else:
                print("Error getting keywords from WriterZen")
                logging.error("Error getting keywords from WriterZen")
                return

    def login(self):
        if self.debug:
            print('Getting session tokens')
        logging.info('Getting session tokens')
        self.session.cookies.clear()
        self.session.headers.pop('X-Xsrf-Token', None)
        url = "https://app.writerzen.net/login"
        response = self.session.get(url)
        token_match = re.search(r'_token" value="(.*?)"', response.text)
        if not token_match:
            raise Exception(
                "_token not found"
            )
        _token = token_match.group(1)
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
        })
        email = os.getenv('WRITERZEN_EMAIL')
        password = os.getenv('WRITERZEN_PASS')
        data = {
            "_token": _token,
            "email": email,
            "password": password,
            "remember": "on"
        }
        if self.debug:
            print('Logging in')
        logging.info('Logging in')
        response = self.session.post(url, data=data)
        if response.status_code != 200:
            raise Exception(
                f"An error occurred logging in. Status code: {response.status_code}"
            )
        response = self.session.get("https://app.writerzen.net/api/services/core/workspaces")
        if response.status_code != 200:
            raise Exception(
                f"An error occurred getting workspace id. Status code: {response.status_code}"
            )
        elif response.json()['status'] != 200:
            raise Exception(
                "An error occurred getting workspace id, status not 200"
            )
        workspace_id = response.json()['data'][0]['id']
        x_xsrf_token = f'{self.session.cookies.get("XSRF-TOKEN")[:-3]}='
        self.session.headers.update({
            "X-Xsrf-Token": x_xsrf_token,
            "Content-Type": "application/json"
        })
        data = {
            "workspace_id": workspace_id
        }
        response = self.session.post("https://app.writerzen.net/api/services/core/workspaces/select", json=data)
        if response.status_code != 200:
            raise Exception(
                f"An error occurred selecting workspace. Status code: {response.status_code}"
            )
        x_xsrf_token = f'{self.session.cookies.get("XSRF-TOKEN")[:-3]}='
        self.session.headers.update({
            "X-Xsrf-Token": x_xsrf_token,
        })
        session_id = self.session.cookies.get("writerzen_session")
        xsrf_token = self.session.cookies.get("XSRF-TOKEN")
        dotenv_path = find_dotenv(env_path)
        set_key(dotenv_path, 'WRITERZEN_SESSION_ID', session_id)
        set_key(dotenv_path, 'WRITERZEN_XSRF_TOKEN', xsrf_token)

        return session_id, xsrf_token


if __name__ == "__main__":
    print(WriterZen(debug=True).get_keywords('facebook ads for realtors'))
