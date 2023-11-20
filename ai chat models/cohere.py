import os
import uuid

import requests
from django.db.models import F
from django.db.models.functions import Coalesce
from jedi.inference.base_value import Value

from scriptsv2.models import ArticleCost
from scriptsv2.utils.usable_function import UsableFunc
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(UsableFunc.paths('env'))


class CohereResponse:
    def __init__(self, response, prompt):
        self.response = response
        self.prompt = prompt
        anthropic = Anthropic()
        self.prompt_token_count = anthropic.count_tokens(self.prompt)
        self.response_token_count = anthropic.count_tokens(self.response)
        self.total_tokens = self.prompt_token_count + self.response_token_count
        self.prompt_cost = round(self.prompt_token_count * 1.5 * 1e-6, 8)
        self.response_cost = round(self.response_token_count * 2 * 1e-6, 8)
        self.cost = round(self.prompt_cost + self.response_cost, 8)

    def __str__(self):
        return str(self.response)


class Cohere:
    def __init__(self, **kwargs):
        self.session = requests.Session()
        self.session.headers.update({
            "accept": "application/json",
            "content-type": "application/json",
            "authorization": f"Bearer {os.getenv('COHERE_API_KEY')}"
        })
        self.max_tokens = 1000
        self.total_cost = 0
        self.keyw_id = kwargs.get('keyw_id', 0)

    def save_total_cost(self):
        try:
            check = ArticleCost.objects.filter(keyw_id=self.keyw_id)

            print(f"CHECK KEYWORD: {self.keyw_id}")
            print(f"TOTAL COST: {self.total_cost}")
            if check:
                print(f"SAVED ARTICLE COST ON KEYWORD: {self.keyw_id}")
                check.update(
                    cohere=Coalesce(F('cohere'), Value(0)) + self.total_cost
                )
            else:
                print(f"SAVED ARTICLE COST ON KEYWORD: {self.keyw_id}")
                ArticleCost.objects.create(
                    keyw_id=self.keyw_id,
                    cohere=self.total_cost
                )
        except Exception as e:
            print(f"COHERE EMPTY KEYWORD PROCEED PROCESS")

    def send_prompt(self, prompt, **settings):
        """
            This generates realistic text conditioned on a given input.
            Refer to https://docs.cohere.com/reference/generate for the correct usage of params
            Available models: command, command-nightly, command-light, and command-light-nightly
            Sample usage:
                result = Cohere().send_prompt('what is python?')
                print(result)
        """
        params_list = ['prompt', 'model', 'num_generations', 'stream', 'max_tokens', 'truncate', 'temperature',
                       'preset', 'end_sequences', 'stop_sequences', 'k', 'p', 'frequency_penalty', 'presence_penalty',
                       'return_likelihoods', 'logit_bias']
        data = {
            "max_tokens": self.max_tokens,
            "truncate": "END",
            "return_likelihoods": "NONE",
            "prompt": prompt
        }
        for key, value in settings.items():
            if key in params_list:
                data[key] = value
            if key == 'prompt':
                prompt = value

        response = self.session.post(
            "https://api.cohere.ai/v1/generate",
            json=data
        )

        result = CohereResponse(response.json()['generations'][0]['text'].strip(), prompt)
        self.total_cost = result.cost
        self.save_total_cost()

        return result

    def send_chat(self, message, conversation_id, **settings):
        """
            The chat allows users to have conversations with a model from Cohere.
            Refer to https://docs.cohere.com/reference/chat-1 for the correct usage of params
            Available models: command, command-nightly, command-light, and command-light-nightly
            Sample usage:
                conversation_id = Cohere.generate_conversation_id()  # create new conversation id first
                result = Cohere().send_chat('what is python?', conversation_id)
                print(result)
                result = Cohere().send_chat('give some examples', conversation_id)
                print(result)
        """
        params_list = ['message', 'model', 'stream', 'preamble_override', 'chat_history', 'conversation_id',
                       'prompt_truncation', 'connectors', 'search_queries_only', 'documents', 'citation_quality',
                       'temperature']
        data = {
            "message": message,
            "conversation_id": conversation_id
        }
        for key, value in settings.items():
            if key in params_list:
                data[key] = value
            if key == 'message':
                message = value

        response = self.session.post(
            "https://api.cohere.ai/v1/chat",
            json=data
        )
        result = CohereResponse(response.json()['text'].strip(), message)

        return result

    @staticmethod
    def generate_conversation_id():
        """ This returns a randomly generated uuid string for unique conversation id """
        return str(uuid.uuid4())

    def summarize(self, text, **settings):
        """
            This generates a summary in English for a given text.
            Refer to https://docs.cohere.com/reference/summarize-2 for the correct usage of params
            Available models: command, command-nightly, command-light, and command-light-nightly
            Sample usage:
                article = '''
                In a serene forest, two inseparable squirrels, Squeaky and Nutty, stumbled upon a glistening
                key one bright morning. Squeaky, cautious by nature, advised leaving it be, fearing
                consequences. But Nutty, driven by boundless curiosity, insisted on trying it. They
                uncovered a hidden chamber filled with treasures, which they shared with their forest
                friends. Yet, as envy and strife tainted their once-harmonious community, Squeaky and
                Nutty realized the cost of curiosity and chose to lock the door, mending their forest's unity.

                In the end, they discovered that true treasures lay not in material wealth but in the enduring
                bonds of friendship and the tranquility of their forest home.
                '''
                result = Cohere().summarize(article)
                print(result)
        """
        params_list = ['text', 'length', 'format', 'model', 'extractiveness', 'temperature', 'additional_command']
        data = {
            "text": text
        }
        for key, value in settings.items():
            if key in params_list:
                data[key] = value
            if key == 'text':
                text = value

        response = self.session.post(
            "https://api.cohere.ai/v1/summarize",
            json=data
        )
        print("SUMMARY", response.json())
        result = CohereResponse(response.json()['summary'].strip(), text)

        self.total_cost = result.cost
        self.save_total_cost()
        return result


if __name__ == "__main__":
    cohere_result = Cohere().send_prompt('what is python?')
    print(cohere_result)
    print(cohere_result.cost)
