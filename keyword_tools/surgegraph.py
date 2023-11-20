import os, re, json

from curl_cffi import requests
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

logging = CustomLogger.log(os.path.join('keyword_tool_scripts', 'surgegraph.log'))

MAX_RETRIES = 5


class SurgeGraph:
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            print('Initialized SurgeGraph')
        logging.info('Initialized SurgeGraph')
        load_dotenv(env_path)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': '*/*',
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "Origin": "https://app.surgegraph.io",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        })
        self.auth_token = os.getenv('SURGEGRAPH_AUTH_TOKEN')

    def get_keywords(self, keyword):
        print('Getting Keywords from SurgeGraph')
        logging.info('Getting Keywords from SurgeGraph')
        for i in range(MAX_RETRIES):
            try:
                url = "https://keyword-research-3imqkyebta-uc.a.run.app/keyword-data/get-rkw"
                self.session.headers.update({
                    "Authorization": f"Bearer {self.auth_token}"
                })
                data = {
                    "keyword": keyword,
                    "location": {
                        "code": 2840,
                        "isoCode": "US"
                    },
                    "languageCode": "en",
                }
                response = self.session.post(url, data=json.dumps(data))
                if response.status_code == 500:
                    if self.debug:
                        print("Authorization token expired")
                    logging.error("Authorization token expired")
                    if i + 1 < MAX_RETRIES:
                        self.auth_token = self._regenerate_auth_token()
                    continue
                if response.status_code != 200:
                    raise Exception(
                        f"Status code: {response.status_code}\nError message: {response.text}"
                    )
                if "success" not in response.json():
                    raise Exception(
                        f"An error occurred getting .\nError message: {response.json()}"
                    )
                keywords = []
                keywords_list = []
                for result in response.json()['relatedKeywords']:
                    if result['keyword'] not in keywords:
                        keywords.append(result['keyword'])
                        keywords_list.append({
                            "keyword": result['keyword'],
                            "search volume": result.get('volume', None),
                            "keyword difficulty": result.get('difficulty', None),
                            "source": "SurgeGraph"
                        })

                print(f'Successfully retrieved {len(keywords_list)} keywords from SurgeGraph')
                logging.info(f'Successfully retrieved {len(keywords_list)} keywords from SurgeGraph')

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
                print("Error getting keywords from SurgeGraph")
                logging.error("Error getting keywords from SurgeGraph")
                return

    def _regenerate_auth_token(self):
        self.session.cookies.clear()
        self.session.headers.pop('Authorization', None)
        if self.debug:
            print('Getting new authorization token')
        logging.info('Getting new authorization token')
        api_key = self._get_api_key()
        url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        params = {
            "key": api_key
        }
        email = os.getenv('SURGEGRAPH_EMAIL')
        password = os.getenv('SURGEGRAPH_PASS')
        data = {
            "returnSecureToken": True,
            "email": email,
            "password": password
        }
        response = self.session.post(url, params=params, json=data, impersonate="chrome110")
        if "idToken" not in response.json():
            raise Exception(
                "Authorization token not found"
            )
        dotenv_path = find_dotenv(env_path)
        set_key(dotenv_path, 'SURGEGRAPH_AUTH_TOKEN', response.json()['idToken'])
        if self.debug:
            print('Getting new authorization successful')
        logging.info('Getting new authorization successful')
        return response.json()['idToken']

    def _get_api_key(self):
        if self.debug:
            print('Getting api key parameter')
        logging.info('Getting api key parameter')
        response = self.session.get("https://app.surgegraph.io/sign-in", impersonate="chrome110")
        main_js_match = re.search(r"main\.(.{16})\.js", response.text)
        if not main_js_match:
            raise Exception(
                "main js not found"
            )
        main_js_link = f"https://app.surgegraph.io/{main_js_match.group(0)}"
        response = self.session.get(main_js_link, impersonate="chrome110")
        api_key_match = re.search(r'apiKey:"(.*?)"', response.text)
        if not api_key_match:
            raise Exception(
                "apiKey not found"
            )

        return api_key_match.group(1)


if __name__ == "__main__":
    print(SurgeGraph(debug=True).get_keywords('car rental san antonio'))
