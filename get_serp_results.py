import requests
import os

from dotenv import load_dotenv, set_key, find_dotenv

from scriptsv2.utils.usable_function import UsableFunc

env_file = UsableFunc.paths('env')

MAX_RETRIES = 3


class Moz:
    def __init__(self):
        print('Moz Initializing')
        load_dotenv(env_file)
        self.session = requests.session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        })
        self.session.cookies.set('_moz_csrf', os.getenv('MOZ_SESSION_ID'))

    def update_session_id(self):
        print('Updating Session ID')
        self.session.cookies.clear()
        response = self.session.get('https://moz.com/login')
        for cookie in response.cookies:
            if cookie.name == "_moz_csrf":
                dotenv_path = find_dotenv(env_file)
                session_id = cookie.value
                set_key(dotenv_path, 'MOZ_SESSION_ID', session_id)
                self.session.cookies.set('_moz_csrf', session_id)

    def get_serp(
        self,
        keyword: str,  # string: keyword on an article
        word_count: int = 1000,  # int: article word count, default is 1000 words if not specified
        lptw: int or float = 1  # float: number of link per thousand words, default is 1 link/1k words if not specified
    ) -> list:  # output is a list, will return empty if encountered an error

        number_of_links = max(int((word_count // 1000) * lptw), 1)
        print(f'Getting serp results of {keyword}')
        for i in range(MAX_RETRIES):
            try:
                url = "https://moz.com/explorer/api/2.5/keyword/analysis"
                payload = {
                    "engine": "google",
                    "keyword": keyword,
                    "locale": "en-US"
                }
                response = self.session.post(url, json=payload)
                if response.status_code in [200, 201]:
                    results = response.json()['serp']['results']
                    url_list = []
                    for result in results:
                        if 'domain_authority' not in result:
                            continue
                        if result['domain_authority'] >= 70:
                            url_list.append(result['url'])
                    if url_list:
                        return url_list[:number_of_links]
                    else:
                        return [result[url] for result in results][:number_of_links]

                elif response.status_code == 403:
                    print("Session ID expired")
                    self.update_session_id()

                else:
                    print(response.text)
                    print(response.status_code)
                    raise Exception

            except Exception as e:
                print(f"An error occurred: {str(e)}")

            if i < MAX_RETRIES-1:
                print("Retrying...")
            else:
                return []


if __name__ == "__main__":
    print(Moz().get_serp('Create AI', word_count=5000))
