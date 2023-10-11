import os
import time

from curl_cffi import requests
from dotenv import load_dotenv

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

logging = CustomLogger.log(os.path.join('keyword_tool_scripts', 'semrush.log'))

MAX_RETRIES = 5

BASE_URL = "https://www.semrush.com/kmtgw/rpc"


class Semrush:
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            print('Initialized Semrush')
        logging.info('Initialized Semrush')
        load_dotenv(env_path)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': '*/*',
            "Connection": "keep-alive",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        })
        self.api_key = os.getenv('SEMRUSH_API_KEY')

    def get_keywords(self, keyword):
        print('Getting Keywords from Semrush')
        logging.info('Getting Keywords from Semrush')
        for i in range(MAX_RETRIES):
            try:
                auth_token = self._get_auth_token(keyword)
                keywords_list = []
                keywords = []
                start_time = time.time()
                page_num = 0
                while time.time()-start_time < 30:
                    page_num += 1
                    data = {
                        "id": 1,
                        "jsonrpc": "2.0",
                        "method": "fts.GetKeywords",
                        "params": {
                            "api_key": self.api_key,
                            "user_id": 15727531,
                            "phrase": keyword,
                            "database": "us",
                            "match_type": 0,
                            "questions_only": False,
                            "groups": [],
                            "filter": {
                                "competition_level": [],
                                "cpc": [],
                                "difficulty": [],
                                "phrase": [],
                                "phrase_include_logic": 0,
                                "results": [],
                                "serp_features": [{
                                    "inverted": False,
                                    "value": []
                                }],
                                "volume": [],
                                "words_count": []
                            },
                            "currency": "USD",
                            "order": {
                                "field": "volume",
                                "direction": 1
                            },
                            "page": {
                                "number": page_num,
                                "size": 100
                            }
                        }
                    }
                    self.session.headers.update({
                        "Authorization": auth_token
                    })
                    response = self.session.post(BASE_URL, json=data)
                    if "error" in response.json():
                        raise Exception(
                            f"Error getting the keywords: {response.json()['error']['message']}"
                        )
                    elif "result" in response.json():
                        for result in response.json()['result']:
                            if result['phrase'] not in keywords:
                                keywords.append(result['phrase'])
                                keywords_list.append({
                                    "keyword": result['phrase'],
                                    "search volume": result.get('volume', None),
                                    "keyword difficulty": result.get('difficulty', None),
                                    "source": "Semrush"
                                })
                        if len(response.json()['result']) < 100:
                            break
                    else:
                        raise Exception(
                            f"Unknown error: {response.status_code}\n {response.text}"
                        )

                print(f'Successfully retrieved {len(keywords_list)} keywords from Semrush')
                logging.info(f'Successfully retrieved {len(keywords_list)} keywords from Semrush')

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
                print("Error getting keywords from Semrush")
                logging.error("Error getting keywords from Semrush")
                return

    def _get_auth_token(self, keyword):
        if self.debug:
            print("Getting auth token")
        logging.info("Getting auth token")
        data = {
            "id": 1,
            "jsonrpc": "2.0",
            "method": "tokens.GetFTSReport",
            "params": {
                "api_key": self.api_key,
                "user_id": 15727531,
                "phrase": keyword,
                "database": "us",
                "match_type": 0,
                "questions_only": False,
                "groups": [],
                "filter": {
                    "competition_level": [],
                    "cpc": [],
                    "difficulty": [],
                    "phrase": [],
                    "phrase_include_logic": 0,
                    "results": [],
                    "serp_features": [{
                        "inverted": False,
                        "value": []
                    }],
                    "volume": [],
                    "words_count": []
                },
                "currency": "USD",
                "order": {
                    "field": "volume",
                    "direction": 1
                }
            }
        }
        response = self.session.post(BASE_URL, json=data)
        if "error" in response.json():
            raise Exception(
                f"Error getting the auth token: {response.json()['error']['message']}"
            )
        elif "result" in response.json():
            return response.json()['result']['token']
        else:
            raise Exception(
                f"Unknown error: {response.status_code}\n {response.text}"
            )


if __name__ == "__main__":
    print(Semrush(debug=True).get_keywords('car rental san antonio'))
