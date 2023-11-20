import os
import re
import requests
import time
import boto3
import json
import concurrent.futures
from dotenv import load_dotenv
from itertools import repeat
from scriptsv2.utils.usable_function import UsableFunc

MAX_RETRIES = 1
load_dotenv(UsableFunc.paths('env'))
os.environ['AWS_ACCESS_KEY_ID'] = os.getenv('BEDROCK_ACCESS_KEY')
os.environ['AWS_SECRET_ACCESS_KEY'] = os.getenv('BEDROCK_SECRET_KEY')

BUCKET_NAME = 'chadix-creds'
FILE_KEY = 'ai_seo_token.json'

prompt_format = """Improve the readability of this sentence:
{sentence}

Here is the paragraph for context:
{paragraph}

Make the sentence simpler. Make it very easy to read. Minimize using adverbs. 
The target audience is {target}, make the tone {tone}, the style is concise, 
the voice is {voice} and the purpose is {purpose}. 
use this formula and make sure that the level of your sentence is not greater than 10
level = round(4.71 * (letters / words) + 0.5 * words / sentences - 21.43)

Wrap the your answer in p element.
Example:
<p>Your sentence here</p>
"""


class AISEO:
    def __init__(
        self,
        audience="High school students",
        content_complexity="Intermediate",
        voice="Balanced",
        tone="Neutral",
        purpose="refine"
    ):
        self.audience = audience
        self.complexity = content_complexity
        self.voice = voice
        self.tone = tone
        self.purpose = purpose
        self.s3 = boto3.client('s3')
        response = self.s3.get_object(
            Bucket=BUCKET_NAME,
            Key=FILE_KEY
        )
        file_content_bytes = response['Body'].read()
        file_content_string = file_content_bytes.decode('utf-8')
        self.access_token = json.loads(file_content_string)
        self.auth_token = self.access_token["access_token"]
        self.refresh_token = self.access_token["refresh_token"]
        if int(time.time())-self.access_token["refresh_time"] > 3500:
            self.auth_token = self._get_new_auth_token()

    def improve_readability(self, article):
        complete_article_parts = article.splitlines()
        article_parts = [(index, part) for index, part in enumerate(complete_article_parts) if part.strip()]
        formatted_article_parts = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for index, result in enumerate(executor.map(self.improve_article_parts, [pair[1] for pair in article_parts])):
                formatted_article_parts.append((article_parts[index][0], result))
                print(len(formatted_article_parts))

        for index, part in formatted_article_parts:
            complete_article_parts[index] = part

        return "\n".join(complete_article_parts)

    def improve_article_parts(self, part):
        if not part.strip():
            return part
        result = self.improve_paragraph(part)

        return result

    def improve_paragraph(self, p):
        if p.startswith(("#", "!")):
            return p
        else:
            sentences = self.get_sentence_from_paragraph(p)
        hard_or_not = []
        with concurrent.futures.ThreadPoolExecutor() as executor:
            for result in executor.map(self.improve_difficult_sentences, repeat(p), sentences):
                hard_or_not.append(result)

        return " ".join(hard_or_not).strip()

    def improve_difficult_sentences(self, p, sentence):
        clean_sentence = re.sub(r'[^a-zA-Z0-9 ]', '', sentence)
        words = len(clean_sentence.split())
        letters = len("".join(clean_sentence.split()))
        level = self.calculate_level(letters, words, 1)

        if words < 14:
            return sentence.strip()
        elif level >= 10:
            tries = 0
            while level >= 10 and tries < 4:
                tries += 1
                improved_sent = self._send_gpt_prompt(sentence, p)
                clean_sentence = re.sub(r'[^a-zA-Z0-9 ]', '', improved_sent)
                words = len(clean_sentence.split())
                letters = len("".join(clean_sentence.split()))
                level = self.calculate_level(letters, words, 1)

            return improved_sent.strip()
        else:
            return sentence.strip()

    @staticmethod
    def get_sentence_from_paragraph(p):
        sentences = p.split(".")
        sentences = [s.strip() + "." for s in sentences if s.strip()]
        return sentences

    @staticmethod
    def calculate_level(letters, words, sentences):
        if words == 0 or sentences == 0:
            return 0
        level = round(4.71 * (letters / words) + 0.5 * words / sentences - 21.43)
        return max(level, 0)

    def improve_sentence(self, p, sentence):
        for _ in range(MAX_RETRIES):
            try:
                payload = {
                  "data": {
                    "type": "improve_sentence_new_openai_chat",
                    "data": {
                      "data": sentence,
                      "version": "text-davinci-002",
                      "target": self.audience,
                      "audience": self.audience,
                      "tone": self.tone,
                      "style": "Concise",
                      "voice": self.voice,
                      "purpose": self.purpose,
                      "contentComplexity": None,
                      "brandVoice": None,
                      "context": p
                    },
                    "cost": 0
                  }
                }
                headers = {
                    "Authorization": f"Bearer {self.auth_token}",
                    "Content-Type": "application/json"
                }
                response = requests.post(
                    "https://us-central1-aiseo-official.cloudfunctions.net/api",
                    json=payload,
                    headers=headers,
                    timeout=60
                )
                if response.status_code != 200:
                    raise Exception(
                        f"Status {response.status_code}"
                    )
                if "error" in response.json():
                    if response.json()["error"]["message"] == "Unauthenticated":
                        self.auth_token = self._get_new_auth_token()
                    raise Exception(
                        "Authorization token expired. Getting new token"
                    )
                return response.json()["result"]["data"]

            except Exception as e:
                pass

        return sentence

    def ai_detection(self, article_to_review):
        payload = {
            "data": {
                "type": "aiDetect",
                "data": {
                    "t1": article_to_review
                }
            }
        }
        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }
        response = requests.post(
            "https://us-central1-aiseo-official.cloudfunctions.net/api",
            json=payload,
            headers=headers,
            timeout=60
        )
        if response.status_code != 200:
            raise Exception(
                f"Status {response.status_code}"
            )
        if "error" in response.json():
            if response.json()["error"]["message"] == "Unauthenticated":
                self.auth_token = self._get_new_auth_token()
            raise Exception(
                "Authorization token expired. Getting new token"
            )
        return response.json()["result"]

    def _get_new_auth_token(self):
        url = "https://securetoken.googleapis.com/v1/token?key=AIzaSyB7crIxnPyOPrigTWmUd-IVBvbIiQ6tOUw"
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.refresh_token
        }
        response = requests.post(url, data=payload)
        access_token = response.json()
        access_token["refresh_time"] = int(time.time())
        self.s3.put_object(
            Bucket=BUCKET_NAME,
            Key=FILE_KEY,
            Body=json.dumps(access_token, indent=2),
            ContentType='application/json'
        )
        return access_token["access_token"]

    def _send_gpt_prompt(self, sentence, paragraph, model="gpt-3.5-turbo-instruct"):
        prompt = prompt_format.format(
            sentence=sentence,
            paragraph=paragraph,
            target=self.audience,
            tone=self.tone,
            voice=self.voice,
            purpose=self.purpose
        )
        messages = [
            {"role": "user", "content": prompt},
        ]
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": 500
        }
        response = requests.post(
            "https://api.openai.com/v1/completions",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {os.getenv('GPT_API_KEY')}"
            }
        )
        if 'choices' not in response.json():
            print(response.json())
            return sentence
        response_text = response.json()["choices"][0]["text"]
        matched = re.search(r"<p>(.*?)</p>", response_text)
        if not matched:
            print("no match here")
            print(response_text)
            return sentence
        else:
            improved_sentence = matched.group(1)
            print(improved_sentence)
            return improved_sentence


if __name__ == "__main__":
    # sentence = "Create your own AI provides dedicated customer support to assist users with any questions or issues they may encounter."
    # paragraph = "Absolutely! Create your own AI provides dedicated customer support to assist users with any questions or issues they may encounter. They offer various channels such as email support, live chat, and an extensive knowledge base to ensure that users receive timely assistance throughout their journey on the platform."
    #
    # result = AISEO()._send_gpt_prompt(sentence, paragraph)
    # print(result)
    with open('sample_article.txt', 'r') as file:
        article = file.read()
    ai_seo = AISEO(audience="grade 7")
    improved_article = ai_seo.improve_readability(article)
    with open('improved_article.txt', 'w') as file:
        file.write(improved_article)