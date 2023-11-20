import os, re, json, random, string, html, time
import concurrent.futures
from requests_toolbelt import MultipartEncoder

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

logging = CustomLogger.log(os.path.join('keyword_tool_scripts', 'keywordtool.log'))

MAX_RETRIES = 5


class KeywordTool:
    def __init__(self, debug=False):
        self.debug = debug
        if self.debug:
            print('Initialized KeywordTool')
        logging.info('Initialized KeywordTool')
        load_dotenv(env_path)
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        })

    def get_keywords(self, keyword):
        print('Getting Keywords from KeywordTool')
        logging.info('Getting Keywords from KeywordTool')
        for i in range(MAX_RETRIES):
            try:
                response = self.session.get("https://keywordtool.io/", impersonate="chrome110")
                kt_token = self.get_kt_token(response.text)
                url = "https://keywordtool.io/google"
                boundary = f"----WebKitFormBoundary{''.join(random.sample(string.ascii_letters + string.digits, 16))}"
                xsrf_cookie = response.cookies.get("XSRF-TOKEN")
                xsrf_token = f"{xsrf_cookie[:-3]}="
                data = {
                    "default_input": "keyword",
                    "category": "web",
                    "keyword": keyword,
                    "location": "0",
                    "country": "GLB",
                    "language": "en",
                }
                m = MultipartEncoder(fields=data, boundary=boundary)
                self.session.headers.update({
                    "Content-Type": m.content_type,
                    "X-Kt-Token": kt_token,
                    "X-Xsrf-Token": xsrf_token,
                    "X-Requested-With": "XMLHttpRequest",
                })
                response = self.session.post(url, data=m.to_string(), impersonate="chrome110")
                redirect_link = response.json()['redirect']
                google_keyword_element = self._get_keyword_element(redirect_link)
                token = google_keyword_element.get('token')
                keywords_total = []
                for index in [1, 3, 6]:
                    filter_token, scrape_urls = self._filter(token, index)
                    if scrape_urls:
                        payload = self._generate_payload(scrape_urls)
                    else:
                        payload = {}
                    data = {"payload": json.dumps(payload, ensure_ascii=False)}
                    self.session.headers.update({
                        "Token": filter_token,
                        "Content-Type": "application/json"
                    })
                    response = self.session.post("https://keywordtool.io/search/keywords/google/keywords", data=json.dumps(data))
                    if response.status_code != 200:
                        raise Exception(
                            f"Status code: {response.status_code} on https://keywordtool.io/search/keywords/google/keywords"
                        )
                    keywords_payload = response.json()['keywords_payload']
                    metrics_url = response.json()['metrics_url']
                    keywords = self._get_metrics(metrics_url, keywords_payload)
                    for keyword in keywords:
                        if not any(unique_keywords.get('keyword') == keyword['keyword'] for unique_keywords in keywords_total):
                            keywords_total.append(keyword)

                print(f'Successfully retrieved {len(keywords_total)} keywords from KeywordTool')
                logging.info(f'Successfully retrieved {len(keywords_total)} keywords from KeywordTool')

                return keywords_total

            except Exception as e:
                if self.debug:
                    print(f"An error occurred: {str(e)}")
                logging.error(f"An error occurred: {str(e)}")

            if i + 1 < MAX_RETRIES:
                if self.debug:
                    print("Retrying...")
                logging.info("Retrying...")
            else:
                print("Error getting keywords from KeywordTool")
                logging.error("Error getting keywords from KeywordTool")
                return

    def get_kt_token(self, response_text):
        if self.debug:
            print('Getting Kt Token')
        logging.info('Getting Kt Token')
        app_js_match = re.search(r"https://keywordtool\.io/build/assets/app-(.{8})\.js", response_text)
        if not app_js_match:
            raise Exception(
                "app js not found"
            )

        if app_js_match.group(0):
            app_js_link = app_js_match.group(0)
        else:
            raise Exception(
                "app js token not found"
            )
        response = self.session.get(app_js_link, impersonate="chrome110")
        token_match = re.search(r'getToken:\(\)=>\"([a-f\d-]+)\"', response.text)
        if not token_match:
            raise Exception(
                "kt token not found"
            )

        if token_match.group(1):
            token = token_match.group(1)
        else:
            raise Exception(
                "kt token not found"
            )
        return token

    def _generate_payload(self, data):
        if self.debug:
            print('Generating keyword payload')
        logging.info('Generating keyword payload')
        url_list = list(data.values())
        data_values = []
        futures = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for url in url_list:
                future = executor.submit(self._fetch_data, url)
                futures.append((url, future))
            for url, future in futures:
                result = future.result()
                if result:
                    data_values.append(result)

        payload_dict = {}
        for keys, values in zip(list(data.keys()), data_values):
            payload_dict[keys] = values

        return payload_dict

    def _fetch_data(self, url):
        response_text = self.session.get(url).text
        data_match = re.search(r"window.google.ac.h\((.*?)\)", response_text)
        if data_match:
            unescaped_data = html.unescape(data_match.group(1))
            data_list = json.loads(unescaped_data)
            return data_list
        return None

    def _get_keyword_element(self, url):
        if self.debug:
            print('Getting element of keyword')
        logging.info('Getting element of keyword')
        response = self.session.get(url, impersonate="chrome110")
        if response.status_code != 200:
            raise Exception(
                f"Status code: {response.status_code} on redirect link"
            )
        html_content = response.content
        soup = BeautifulSoup(html_content, 'html.parser')
        google_keyword_element = soup.find('google-keywords')
        if not google_keyword_element:
            raise Exception(
                "Google Keyword element not found"
            )
        return google_keyword_element

    def _get_metrics(self, url, payload):
        if self.debug:
            print('Getting metrics of keyword')
        logging.info('Getting metrics of keyword')
        start_time = time.time()
        keywords_list = []
        keywords = []
        start_total = 0
        while time.time()-start_time < 30:
            data = {
                "filter_keywords": "",
                "filter_keywords_partial_match": "",
                "negative_keywords": "",
                "keywords_payload": payload,
                "sort": "searchVolumeDesc",
                "total": start_total
            }
            response = self.session.post(url, data=json.dumps(data))
            if response.status_code != 200:
                raise(
                    f"Status code: {response.status_code} when getting metrics"
                )
            keywords_data = response.json()['keywords']
            total_keywords = response.json()['search_total_keywords']
            for keyword in keywords_data:
                if keyword['keyword_source'] not in keywords:
                    keywords.append(keyword['keyword_source'])
                    keywords_list.append({
                        "keyword": keyword['keyword_source'],
                        "search volume": keyword.get('search_volume', None),
                        "keyword difficulty": keyword.get('competition', None),
                        "source": "KeywordTool"
                    })
            if total_keywords > start_total:
                start_total += 100
                continue
            break

        return keywords_list

    def _filter(self, token, filter_index):
        if self.debug:
            print('Filtering keyword')
        logging.info('Filtering keyword')
        self.session.headers.update({
            "Token": token,
            "Content-Type": "application/json"
        })
        data = {
            "search_type": filter_index,
        }
        response = self.session.post("https://keywordtool.io/search/keywords/google/filter", data=json.dumps(data))

        filter_token = response.json()['token']
        scrape_urls = response.json()['scrape_urls']

        return filter_token, scrape_urls


if __name__ == "__main__":
    result = KeywordTool(debug=True).get_keywords('facebook ads for realtors')
    print(result)
    print(len(result))
    # ATP().login()
