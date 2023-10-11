import os

from curl_cffi import requests
from dotenv import load_dotenv
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

logging = CustomLogger.log(os.path.join('keyword_tool_scripts', 'keywordchef.log'))

MAX_RETRIES = 5


class KeywordChef:
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            print('Initialized KeywordChef')
        logging.info('Initialized KeywordChef')
        load_dotenv(env_path)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': '*/*',
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        })
        self.session_id = os.getenv('KEYWORDCHEF_SESSION_ID')

    def get_keywords(self, keyword):
        print('Getting Keywords from KeywordChef')
        logging.info('Getting Keywords from KeywordChef')
        for i in range(MAX_RETRIES):
            try:
                url = "https://app.keywordchef.com/Discover/GetKeywordResultsPreview"
                self.session.cookies.set(".AspNetCore.Identity.Application", self.session_id)
                self.session.headers.update({
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                })
                prompt = "+".join(keyword.split(" "))
                data = f"searchTerm={prompt}*&countryCode=us&category=wildcard"
                response = self.session.post(url, data=data, impersonate="chrome110")
                if response.status_code != 200:
                    raise Exception(
                        f"Status {response.status_code}"
                    )
                html_content = response.content
                soup = BeautifulSoup(html_content, 'html.parser')
                elements = soup.select('tbody tr')
                if elements:
                    keywords = []
                    keywords_list = []
                    for element in elements:
                        keyword = element.text.strip()
                        if keyword != "" or keyword not in keywords:
                            keywords.append(keyword)
                            keywords_list.append({
                                "keyword": keyword,
                                "search volume": None,
                                "keyword difficulty": None,
                                "source": "KeywordChef"
                            })

                    print(f'Successfully retrieved {len(keywords_list)} keywords from KeywordChef')
                    logging.info(f'Successfully retrieved {len(keywords_list)} keywords from KeywordChef')

                    return keywords_list

                else:
                    raise Exception(
                        "No keywords found"
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
                print("Error getting keywords from KeywordChef")
                logging.error("Error getting keywords from KeywordChef")
                return


if __name__ == "__main__":
    print(KeywordChef(debug=True).get_keywords('car rental san antonio'))
    # KeywordChef().login()
