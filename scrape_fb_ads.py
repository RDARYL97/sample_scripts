import requests
from bs4 import BeautifulSoup
import concurrent.futures
import json
from urllib.parse import urlparse
from requests.exceptions import ProxyError, ConnectTimeout
import haversine as hs
from lxml import etree
import re
import html
import csv
import os
import time
from fake_useragent import UserAgent
from dotenv import load_dotenv
from tqdm import tqdm


class FBScraper:
    def __init__(self):
        load_dotenv()
        proxy_url = os.getenv('PROXY')
        self.proxy = {
            'http': proxy_url,
            'https': proxy_url
        }
        self.result_dict = {}
        self.progress_bar = None
        self.ua = UserAgent()

    def generate_ads(self, q, r):
        self.progress_bar = tqdm(desc='Initializing', ncols=100)
        c = self.get_coordinates(q)
        self.get_pages(q, r, c)
        self.get_fb_links()
        self.get_page_ids()
        self.get_ads()
        self.export_results(q)
        self.progress_bar.close()

    def get_coordinates(self, q):
        url = 'https://www.google.com/maps/search/' + q.replace(' ', '+')
        retry_count = 0  # Initialize retry count for each iteration
        self.progress_bar.set_description('Searching the location')
        while retry_count < 3:
            try:
                response = requests.get(url, timeout=10)
                html_content = response.content
                # Save the response content to a file
                soup = BeautifulSoup(html_content, 'html.parser')

                link_element = soup.find_all('script')[6]
                final_list_match = re.search(r'window\.APP_INITIALIZATION_STATE=\[\[(.*?),\[', link_element.text).group(1)
                final_list = json.loads(final_list_match)
                coordinates = [final_list[2], final_list[1]]
                return coordinates
            except (ConnectTimeout, ProxyError, Exception) as e:
                # print(f'Error occurred: {type(e).__name__} - {e}')
                retry_count += 1

    def get_pages(self, q, r, c):
        self.progress_bar.set_description('Getting pages')
        total_pages = []
        for i in range(10):
            retry_count = 0  # Initialize retry count for each iteration
            prev_page_number = len(total_pages)
            while retry_count < 3:
                try:
                    url = 'https://www.google.com/search'
                    headers = {
                        "User-Agent": self.ua.random
                    }
                    params = {
                        "tbm": "map",
                        "authuser": 0,
                        "hl": "en",
                        "gl": "ph",
                        "pb": f"!4m12!1m3!1d{0}!2d{c[0]}!3d{c[1]}!2m3!1f0!2f0!3f0!3m2!1i1920!2i953!4f13.1!7i20!8i{20 * i}!10b1!12m31!1m1!18b1!2m3!5m1!6e2!20e3!6m12!4b1!49b1!63m0!73m0!74i150000!75b1!85b1!89b1!91b1!110m0!114b1!149b1!10b1!12b1!13b1!14b1!16b1!17m1!3e1!20m4!5e2!6b1!8b1!14b1!19m4!2m3!1i360!2i120!4i8!20m57!2m2!1i203!2i100!3m2!2i4!5b1!6m6!1m2!1i86!2i86!1m2!1i408!2i240!7m42!1m3!1e1!2b0!3e3!1m3!1e2!2b1!3e2!1m3!1e2!2b0!3e3!1m3!1e8!2b0!3e3!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2!1m3!1e9!2b1!3e2!1m3!1e10!2b0!3e3!1m3!1e10!2b1!3e2!1m3!1e10!2b0!3e4!2b1!4b1!9b0!22m2!1stest!7e81!24m78!1m26!13m9!2b1!3b1!4b1!6i1!8b1!9b1!14b1!20b1!25b1!18m15!3b1!4b1!5b1!6b1!13b1!14b1!15b1!17b1!21b1!22b0!25b1!27m1!1b0!28b0!30b0!2b1!5m5!2b1!5b1!6b1!7b1!10b1!10m1!8e3!11m1!3e1!14m1!3b1!17b1!20m2!1e3!1e6!24b1!25b1!26b1!29b1!30m1!2b1!36b1!39m3!2m2!2i1!3i1!43b1!52b1!54m1!1b1!55b1!56m2!1b1!3b1!65m5!3m4!1m3!1m2!1i224!2i298!71b1!72m4!1m2!3b1!5b1!4b1!89b1!103b1!113b1!26m4!2m3!1i80!2i92!4i8!30m28!1m6!1m2!1i0!2i0!2m2!1i530!2i953!1m6!1m2!1i1870!2i0!2m2!1i1920!2i953!1m6!1m2!1i0!2i0!2m2!1i1920!2i20!1m6!1m2!1i0!2i933!2m2!1i1920!2i953!34m19!2b1!3b1!4b1!6b1!7b1!8m6!1b1!3b1!4b1!5b1!6b1!7b1!9b1!12b1!14b1!20b1!23b1!25b1!26b1!37m1!1e81!42b1!46m1!1e1!47m0!49m6!3b1!6m2!1b1!2b1!7m1!1e3!50m25!1m21!2m7!1u3!4stest!5e1!9stest!10m2!3m1!1e1!2m7!1u2!4stest!5e1!9stest!10m2!2m1!1e1!3m1!1u3!3m1!1u2!4BIAE!2e2!3m1!3b1!59BQ2dBd0Fn!67m3!7b1!10b1!14b0!69i653",
                        "q": q,
                        "tch": 1,
                        "ech": i + 1,
                    }
                    response = requests.get(url, params=params, headers=headers, timeout=10)
                    page_dict = json.loads(response.text.replace('/*""*/', '').replace(")]}'", ''))
                    page_list_string = json.loads(page_dict['d'])
                    page_list = page_list_string[0][1][1:]
                    for page in page_list:
                        page_name = page[-1][11]
                        page_coordinates = page[-1][9][2:]
                        distance = hs.haversine(c, page_coordinates) * 0.621371
                        if page_name not in total_pages and page[-1][7] and r > distance:
                            page_link = page[-1][7][0].replace("/url?q=", "")
                            parsed_url = urlparse(page_link)
                            main_link = parsed_url.scheme + "://" + parsed_url.netloc
                            if page[-1][2] is not None:
                                page_address = " ".join(page[-1][2])
                            else:
                                page_address = None
                            total_pages.append(page_name)
                            self.result_dict[page_name] = {
                                'website': main_link,
                                'address': page_address,
                                'distance': distance
                            }
                            self.progress_bar.set_description(f"{len(self.result_dict)} pages found")
                            self.progress_bar.reset(total=len(self.result_dict))
                    break

                except (ConnectTimeout, ProxyError, Exception) as e:
                    # print(f'Error occurred: {type(e).__name__} - {e}')
                    retry_count += 1

            if len(self.result_dict) == prev_page_number:
                break

    def process_website(self, page_name, url):
        retry_count = 0
        while retry_count < 3:
            headers = {
                "User-Agent": self.ua.random
            }
            try:
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    html_content = response.content
                    # Save the response content to a file
                    soup = BeautifulSoup(html_content, 'html.parser')
                    root = etree.HTML(str(soup))

                    elements = root.xpath('//*[contains(@href, "facebook.com") or contains(@href, "fb.com")]')
                    if elements:
                        fb_link = elements[0].get('href')
                        if fb_link not in ["http://facebook.com", "http://www.facebook.com", "http://fb.com",
                                           "http://www.fb.com"]:
                            self.result_dict[page_name]['fb page link'] = fb_link
                    break
                retry_count += 1
            except Exception as e:
                # print(f'Error occurred: {type(e).__name__} - {e}')
                retry_count += 1
        self.progress_bar.update(1)
        self.progress_bar.set_description(f"Searching website: {url}")

    def get_fb_links(self):
        self.progress_bar.set_description("Searching website")
        thread_pool_size = min(10, len(self.result_dict))  # Set the maximum number of concurrent threads
        threads = []
        if thread_pool_size > 0:
            with concurrent.futures.ThreadPoolExecutor(max_workers=thread_pool_size) as executor:
                for page_name, result_list in self.result_dict.items():
                    url = result_list['website']
                    thread = executor.submit(self.process_website, page_name, url)
                    threads.append(thread)
                # Wait for all threads to complete
                for thread in concurrent.futures.as_completed(threads):
                    thread.result()

        to_be_deleted = []
        for page_name, value_dict in self.result_dict.items():
            if 'fb page link' not in value_dict:
                to_be_deleted.append(page_name)
        for page in to_be_deleted:
            self.result_dict.pop(page)

    def process_page_id(self, page_name, url):
        retry_count = 0
        self.progress_bar.set_description(f"Searching facebook page: {url}")
        while retry_count < 3:
            try:
                session = requests.session()
                response = session.get(url, timeout=5)
                if response.status_code != 200:
                    raise Exception(
                        "Status not 200"
                    )
                text = response.text
                token_match = re.search(r'"LSD",\[],\{"token":"(.*?)"', text)
                if not token_match:
                    raise Exception(
                        "token not found"
                    )
                token = token_match.group(1)
                try:
                    comet_req = re.search(r'__comet_req=(.*?)&', text).group(1)
                except:
                    comet_req = 15
                route_url = "".join(url.split('.com')[1:])
                if route_url.strip():
                    if route_url[-1] == '/':
                        route_url = route_url[:-1].replace('/', '%2F')
                    else:
                        route_url = route_url.replace('/', '%2F')
                    url2 = 'https://www.facebook.com/ajax/bulk-route-definitions/'
                    session.headers.update({
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Fb-Lsd": token
                    })
                    payload = {
                        "route_urls[10]": f"{route_url}/videos",
                        "__a": 1,
                        "lsd": token,
                        "__comet_req": comet_req,
                    }
                    response2 = session.post(url2, data=payload, proxies=self.proxy)
                    if response2.status_code != 200:
                        raise Exception(
                            "Status not 200"
                        )
                    if '"pageID":"' in response2.text:
                        page_id = re.search(r'"pageID":"(.*?)"', response2.text).group(1)
                        self.result_dict[page_name]['page id'] = page_id
                break

            except Exception as e:
                # print(f'An error occured: {type(e).__name__} - {e}')
                retry_count += 1
        self.progress_bar.update(1)

    def get_page_ids(self):
        self.progress_bar.reset(total=len(self.result_dict))
        self.progress_bar.set_description("Searching facebook pages")
        thread_pool_size = min(10, len(self.result_dict))  # Set the maximum number of concurrent threads
        threads = []
        if thread_pool_size > 0:
            with concurrent.futures.ThreadPoolExecutor(max_workers=thread_pool_size) as executor:
                for page_name, result_list in self.result_dict.items():
                    url = result_list['fb page link']
                    thread = executor.submit(self.process_page_id, page_name, url)
                    threads.append(thread)

                # Wait for all threads to complete
                for thread in concurrent.futures.as_completed(threads):
                    thread.result()

        to_be_deleted = []
        for page_name, value_dict in self.result_dict.items():
            if 'page id' not in value_dict:
                to_be_deleted.append(page_name)
        for page in to_be_deleted:
            self.result_dict.pop(page)

    def process_ads(self, page_name, page_id):
        retry_count = 0
        while retry_count < 3:
            try:
                session = requests.session()
                url = f'https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country=ALL&view_all_page_id={page_id}&search_type=page&media_type=all'
                headers = {
                    "User-Agent": self.ua.random,
                    "Cache-Control": "no-cache"
                }
                response = session.get(url, headers=headers)
                if response.status_code != 200:
                    raise Exception(
                        "Status code not 200"
                    )
                text = response.text
                token_match = re.search(r'"LSD",\[],\{"token":"(.*?)"', text)
                if not token_match:
                    raise Exception(
                        "token not found"
                    )
                token = token_match.group(1)
                url = f"https://www.facebook.com/ads/library/async/search_ads/"
                params = {
                    "count": 30,
                    "active_status": "all",
                    "ad_type": "all",
                    "countries[0]": "ALL",
                    "view_all_page_id": page_id,
                    "media_type": "all",
                    "search_type": "page"
                }

                payload = {
                    "__a": 1,
                    "lsd": token,
                }

                session.headers.update({"Content-Type": "application/x-www-form-urlencoded"})
                session.headers.update({"X-Fb-Lsd": token})

                response = session.post(url, params=params, data=payload, proxies=self.proxy)
                if response.status_code != 200:
                    raise Exception(
                        "Status code not 200"
                    )
                if '"error":3252001' in response.text:
                    raise Exception(
                        "An error occurred getting ads"
                    )
                dictionary = json.loads(response.text.split('(;;);')[1])
                if dictionary['payload'] is not None and 'results' in dictionary['payload']:
                    total_ad_dict = dictionary['payload']['results']
                    if total_ad_dict:
                        ads_list = []
                        for ad_groups in total_ad_dict[:20]:
                            for ad_dict in ad_groups:
                                if ad_dict['isActive'] and ('display_format' in ad_dict['snapshot']):
                                    display_format = ad_dict['snapshot']['display_format']
                                    if display_format in ["video", "image", "carousel"]:
                                        html_body = ad_dict['snapshot']['body']['markup']['__html']
                                        ad_body = html.unescape(html_body)
                                        if display_format == "video":
                                            ad_media = ad_dict['snapshot']['videos'][0]['video_hd_url']
                                            if ad_media.strip() == "":
                                                ad_media = ad_dict['snapshot']['cards'][0]['video_sd_url']
                                        elif display_format == "image":
                                            ad_media = ad_dict['snapshot']['images'][0]['original_image_url']
                                        else:
                                            ad_media = ad_dict['snapshot']['cards'][0]['original_image_url']
                                        if display_format == "carousel":
                                            ad_headline = ad_dict['snapshot']['cards'][0]['title']
                                            ad_link = ad_dict['snapshot']['cards'][0]['link_url']
                                        else:
                                            ad_headline = ad_dict['snapshot']['title']
                                            ad_link = ad_dict['snapshot']['link_url']
                                        ads_list.append({
                                            "ad_copy": ad_body,
                                            "media": ad_media,
                                            "headline": ad_headline,
                                            "button_link": ad_link
                                        })
                                    else:
                                        html_body = ad_dict['snapshot']['cards'][0]['body']
                                        ad_body = html.unescape(html_body)
                                        ad_media = ad_dict['snapshot']['cards'][0]['original_image_url']
                                        if ad_media is None:
                                            ad_media = ad_dict['snapshot']['cards'][0]['video_hd_url']
                                            if ad_media.strip() == "":
                                                ad_media = ad_dict['snapshot']['cards'][0]['video_sd_url']
                                        ad_headline = ad_dict['snapshot']['cards'][0]['title']
                                        ad_link = ad_dict['snapshot']['cards'][0]['link_url']
                                        ads_list.append({
                                            "ad_copy": ad_body,
                                            "media": ad_media,
                                            "headline": ad_headline,
                                            "button_link": ad_link
                                        })
                                    break
                        if ads_list:
                            self.result_dict[page_name]['ads'] = ads_list
                    break

            except Exception as e:
                # print(f'Error occurred: {type(e).__name__} - {e}')
                retry_count += 1

        self.progress_bar.update(1)
        self.progress_bar.set_description(f"Searching ad library of {page_name}")

    def get_ads(self):
        self.progress_bar.reset(total=len(self.result_dict))
        self.progress_bar.set_description("Searching ad library")
        thread_pool_size = min(5, len(self.result_dict))  # Set the maximum number of concurrent threads
        threads = []
        if thread_pool_size > 0:
            with concurrent.futures.ThreadPoolExecutor(max_workers=thread_pool_size) as executor:
                for page_name, result_list in self.result_dict.items():
                    page_id = result_list['page id']
                    thread = executor.submit(self.process_ads, page_name, page_id)
                    threads.append(thread)

                # Wait for all threads to complete
                for thread in concurrent.futures.as_completed(threads):
                    thread.result()

            # Remove the keys marked for deletion
        to_be_deleted = []
        for page_name, value_dict in self.result_dict.items():
            if 'ads' not in value_dict:
                to_be_deleted.append(page_name)
        for page in to_be_deleted:
            self.result_dict.pop(page)

        # print(self.result_dict)

    def export_results(self, q):
        suffix = 1
        niche_name = "_".join(q.split(" ")).lower()
        export_folder = 'export'
        if not os.path.exists(export_folder):
            os.makedirs(export_folder)
        file_name = f"{niche_name}.csv"
        file_path = os.path.join(export_folder, file_name)
        while os.path.exists(file_path):
            # Append the numerical suffix to the new file name
            file_name = f"{niche_name}_{suffix}.csv"
            file_path = os.path.join(export_folder, file_name)
            suffix += 1
        total_ads = 0
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["FB Page", "Location", "FB Page URL", "Ad Copy", "Media", "Headline", "Button URL"])
            for page_name, result_list in self.result_dict.items():
                for ads in result_list['ads']:
                    ad_copy = ads['ad_copy'] if 'ad_copy' in ads else None
                    media = ads['media'] if 'media' in ads else None
                    headline = ads['headline'] if 'headline' in ads else None
                    button_url = ads['button_link'] if 'button_link' in ads else None
                    writer.writerow([page_name, result_list['address'], result_list['fb page link'], ad_copy, media, headline, button_url])
                    total_ads += 1
        self.progress_bar.set_description(f"{total_ads} unique ads found. Exported to {file_name}")


if __name__ == '__main__':
    niche = input("Give a niche: ")
    location = input("Set a location: ")
    radius = int(input("Set a radius in miles: "))
    search_string = f"{niche} in {location}"
    start_time = time.time()
    FBScraper().generate_ads(search_string, radius)
    duration = time.time() - start_time
    minutes, seconds = divmod(duration, 60)
    print(f"Duration: {int(minutes)} minute(s) {int(seconds)} second(s)")
