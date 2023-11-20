import os, re, time, random

from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv, find_dotenv, set_key
import undetected_chromedriver as uc
import requests

from scriptsv2.utils.selenium.error_handler import SeleniumHandler
from scriptsv2.utils.usable_function import UsableFunc

env_path = UsableFunc.paths('env')
secrets_path = UsableFunc.paths('secrets')


class Lumen5:
    def __init__(self):
        self.session = requests.session()
        load_dotenv(env_path)
        self.chrome_options = uc.ChromeOptions()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument("--disable-notifications")
        self.chrome_options.add_argument("--disable-popup-blocking")
        self.chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        self.chrome_options.add_argument("--use-fake-ui-for-media-stream")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('disable-blink-features=AutomationControlled')
        self.chrome_options.add_experimental_option('prefs', {
            "profile.default_content_settings.popups": 0,
            'download.directory_upgrade': True,
            'download.default_directory': "/dev/null",
            "download.prompt_for_download": False,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        })
        self.email = os.getenv('LUMEN_EMAIL')
        self.password = os.getenv('LUMEN_PASSWORD')
        self.session_id = os.getenv('LUMEN_SESSION_ID')
        self.session.headers.update({
            "Accept": "*/*",
            "Connection": "keep-alive",
            "Cookie": f"sessionid={self.session_id}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
        })

    def generate_video(self, article_link):
        self._check_session_id()
        driver = uc.Chrome(options=self.chrome_options)
        driver.get('https://lumen5.com')
        driver.set_window_size(1920, 1080)
        driver.add_cookie({
            'name': 'sessionid',
            'value': self.session_id,
        })
        print('Going to dashboard page')
        driver.get('https://lumen5.com/dashboard/')
        SeleniumHandler.click_until_max_retries(
            driver,
            max_retries=3,
            xpath='//li[contains(@class, "project-list-item")]//*[text()="Daryl"]',
            wait_element_time=10
        )
        print('Creating video')
        SeleniumHandler.click_until_max_retries(
            driver,
            max_retries=3,
            xpath='//*[@data-testid="dashboard_create_video_button"]',
            wait_element_time=10
        )
        print('Choosing template')
        templates = SeleniumHandler.locate_until_max_retries(
            driver,
            max_retries=3,
            xpath='//video[@poster]',
            wait_element_time=10,
            condition=EC.visibility_of_all_elements_located
        )
        template = random.choice(templates)
        SeleniumHandler.click_until_max_retries(
            driver,
            max_retries=3,
            wait_element_time=10,
            element=template
        )
        SeleniumHandler.click_until_max_retries(
            driver,
            max_retries=3,
            xpath='//*[text()="Use this template"]',
            wait_element_time=10
        )
        SeleniumHandler.click_until_max_retries(
            driver,
            max_retries=3,
            xpath='//*[contains(text(), "Transform your text")]',
            wait_element_time=10
        )
        url_input_window = SeleniumHandler.locate_until_max_retries(
            driver,
            max_retries=3,
            xpath='//input[@placeholder="Paste your URL here"]',
            wait_element_time=10,
        )
        print('Importing article')
        url_input_window.send_keys(article_link)
        SeleniumHandler.click_until_max_retries(
            driver,
            max_retries=3,
            xpath='//button/*[text()="Import"]',
            wait_element_time=10
        )
        SeleniumHandler.click_until_max_duration(
            driver,
            max_duration=600,
            xpath='//button[@class="lumen5-button btn btn-rounded btn-primary btn-md"]/*[text()="Continue with AI"]',
            wait_element_time=10
        )
        print('Converting to video')
        SeleniumHandler.click_until_max_duration(
            driver,
            max_duration=600,
            xpath='//button[@class="lumen5-button btn btn-rounded btn-primary btn-md"]/*[text()="Convert to video"]',
            wait_element_time=10
        )
        SeleniumHandler.accept_alert(driver, raise_error=False)
        print('Adding slides')
        prev_video_duration = 0
        total_seconds = 0
        timer = time.time()
        while (time.time()-timer) < 10:
            if prev_video_duration != total_seconds:
                timer = time.time()
                prev_video_duration = total_seconds
            video_duration = SeleniumHandler.locate_until_max_retries(
                driver,
                max_retries=3,
                xpath='//div[@class="time-value"]',
                wait_element_time=10,
                condition=EC.presence_of_element_located
            ).text
            minutes, seconds = map(int, video_duration.split(":"))
            total_seconds = minutes * 60 + seconds
            time.sleep(1)
        print('Publishing')
        SeleniumHandler.click_until_max_duration(
            driver,
            max_duration=600,
            xpath='//button[@id="publish-button"]',
            wait_element_time=10
        )
        SeleniumHandler.accept_alert(driver, max_duration=30, raise_error=False)
        print('Rendering video')
        download_button = SeleniumHandler.locate_until_max_duration(
            driver,
            max_duration=600,
            xpath='//a[contains(@href, ".mp4")]',
            wait_element_time=10
        )
        video_link = download_button.get_attribute("href")

        driver.quit()
        print('Successfully generated video')
        return video_link

    def _update_session_id(self):
        print("Updating session id")
        url = 'https://lumen5.com/complete/email/'
        self.session.headers.update({
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
        })
        payload = {
            "email": self.email,
            "password": self.password,
        }
        response = self.session.post(url, data=payload, allow_redirects=True)
        for redirect_response in response.history:
            for cookie in redirect_response.cookies:
                if cookie.name == "sessionid":
                    self.session_id = cookie.value
                    self.session.headers.update({
                        "Cookie": f"sessionid={self.session_id}"
                    })
                    dotenv_path = find_dotenv(env_path)
                    set_key(dotenv_path, 'LUMEN_SESSION_ID', self.session_id)
                    print(f"Session id updated to {self.session_id}")
                    return

        else:
            print(response.status_code)

    def _check_session_id(self):
        url = "https://lumen5.com/app/"
        response = self.session.get(url)
        if response.status_code == 200:
            pattern = r"<title>(.*?)<\/title>"
            match = re.search(pattern, response.text)
            if match:
                title = match.group(1)
                if title == "Login | Lumen5":
                    self._update_session_id()
                elif title == "Create a Video | Lumen5":
                    return
                else:
                    print(f"Unknown redirect page: {title}")


if __name__ == "__main__":
    start = time.time()
    article = "https://txcarrent.com/san-antonio-sports-car-rental/"
    print(Lumen5().generate_video(article))
    print(time.time()-start)
