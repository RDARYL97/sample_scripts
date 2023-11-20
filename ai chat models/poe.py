import json
import random
import string
from re import search
from time import sleep
from httpx import Client
from scriptsv2.logs.logs_config import CustomLogger
from scriptsv2.utils.usable_function import UsableFunc
from scriptsv2.utils.progressbar.progress_icon import ProgressBar

logging = CustomLogger.log('poe.log')

accounts_json_path = UsableFunc.paths('quora')

BOTS_LIST = {
    'Assistant': 'capybara',
    'Claude-instant-100k': 'a2_100k',
    'Claude-2-100k': 'a2_2',
    'Claude-instant': 'a2',
    'ChatGPT': 'chinchilla',
    # 'ChatGPT-16k': 'agouti',
    # 'GPT-4': 'beaver',
    # 'GPT-4-32k': 'vizcacha',
    'Google-PaLM': 'acouchy',
    'Llama-2-7b': 'llama_2_7b_chat',
    'Llama-2-13b': 'llama_2_13b_chat',
    'Llama-2-70b': 'llama_2_70b_chat',
    'Code-Llama-7b': 'code_llama_7b_instruct',
    'Code-Llama-13b': 'code_llama_13b_instruct',
    'Code-Llama-34b': 'code_llama_34b_instruct',
    'Vicuna-13B-V13': 'vicuna13bv13'
}

QUERIES = {
    "chatHelpers_addMessageBreakEdgeMutation_Mutation": "9450e06185f46531eca3e650c26fa8524f876924d1a8e9a3fb322305044bdac3",
    "ChatHelpersSendNewChatMessageMutation": "943e16d73c3582759fa112842ef050e85d6f0048048862717ba861c828ef3f82",
    "ChatPageQuery": "63eee0aafc4d83a50fe7ceaec1853b191ea86b3d561268fa7aad24c69bb891d9",
    "ChatsHistoryPageQuery": "050767d78f19014e99493016ab2b708b619c7c044eebd838347cf259f0f2aefb",
    "DeleteMessageMutation": "8d1879c2e851ba163badb6065561183600fc1b9de99fc8b48b654eb65af92bed",
    "DeleteUserMessagesMutation": "3f60d527c3f636f308b3a26fc3a0012be34ea1a201e47a774b4513d8a1ba8912"
}

MAX_RETRIES = 3


def bot_map(bot):
    if bot in BOTS_LIST:
        return BOTS_LIST[bot]
    return bot.lower().replace(' ', '')


def generate_nonce(length: int = 16):
    characters = string.ascii_letters + string.digits
    random_string = ''.join(random.choice(characters) for _ in range(length))
    return random_string


def generate_payload(query_name, variables) -> str:
    payload = {
        "queryName": query_name,
        "variables": variables,
        "extensions": {
            "hash": QUERIES[query_name]
        }
    }
    return json.dumps(payload, separators=(",", ":"))


class PoeApi:
    BASE_URL = 'https://www.quora.com'
    HEADERS = {
        'Host': 'www.quora.com',
        'Accept': '*/*',
        'apollographql-client-version': '1.1.6-65',
        'Accept-Language': 'en-US,en;q=0.9',
        'User-Agent': 'Poe 1.1.6 rv:65 env:prod (iPhone14,2; iOS 16.2; en_US)',
        'apollographql-client-name': 'com.quora.app.Experts-apollo-ios',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
    }
    FORMKEY_PATTERN = r'formkey": "(.*?)"'

    def __init__(self, index=None):
        print('Initialized PoeAPI')
        logging.info('Initialized PoeAPI')
        with open(accounts_json_path, "r") as json_file:
            accounts = json.load(json_file)
        if index:
            account = accounts[index]
        else:
            account = random.choice(accounts)
        cookie = account['token']
        print(account['email'])
        logging.info(f"Using account: {account['email']}")
        self.client = Client(timeout=300)
        self.client.cookies.set('m-b', cookie)
        self.client.headers.update({
            **self.HEADERS,
            'Quora-Formkey': self.get_formkey(),
        })
        self.purge_all_conversations()

    def __del__(self):
        self.client.close()

    def get_formkey(self):
        response = self.client.get(self.BASE_URL, headers=self.HEADERS, follow_redirects=True)
        formkey = search(self.FORMKEY_PATTERN, response.text)[1]
        return formkey

    def send_request(self, path: str, query_name: str = "", variables: dict = {}):
        payload = generate_payload(query_name, variables)
        response = self.client.post(f'{self.BASE_URL}/poe_api/{path}', data=payload,
                                    headers={'Content-Type': 'application/x-www-form-urlencoded'})
        return response.json()

    def send_query(self, path: str, data: dict):
        response = self.client.post(f'{self.BASE_URL}/poe_api/{path}', json=data)
        return response.json()

    def get_chat_history(self, bot: str = None, handle: str = "", useBot: bool = False):
        print('Getting chat history')
        logging.info('Getting chat history')
        variables = {'handle': handle, 'useBot': useBot}
        response_json = self.send_request('gql_POST', 'ChatsHistoryPageQuery', variables)
        edges = response_json['data']['chats']['edges']

        chat_bots = {}

        if bot == None:
            print('-' * 18 + ' \033[38;5;121mChat History\033[0m ' + '-' * 18)
            print(
                '\033[38;5;121mChat ID\033[0m  |     \033[38;5;121mChat Code\033[0m       | \033[38;5;121mBot Name\033[0m')
            print('-' * 50)
            for edge in edges:
                chat = edge['node']
                model = bot_map(chat["defaultBotObject"]["displayName"])
                print(f'{chat["chatId"]} | {chat["chatCode"]} | {model}')
                if model in chat_bots:
                    chat_bots[model].append({"chatId": chat["chatId"], "chatCode": chat["chatCode"], "id": chat["id"]})
                else:
                    chat_bots[model] = [{"chatId": chat["chatId"], "chatCode": chat["chatCode"], "id": chat["id"]}]
            print('-' * 50)
        else:
            for edge in edges:
                chat = edge['node']
                try:
                    model = bot_map(chat["defaultBotObject"]["displayName"])
                    if model == bot:
                        if model in chat_bots:
                            chat_bots[model].append(
                                {"chatId": chat["chatId"], "chatCode": chat["chatCode"], "id": chat["id"]})
                        else:
                            chat_bots[model] = [
                                {"chatId": chat["chatId"], "chatCode": chat["chatCode"], "id": chat["id"]}]
                except:
                    pass
        return chat_bots

    def create_new_chat(self, bot: str = "", message: str = ""):
        print('Creating new chat')
        logging.info('Creating new chat')
        variables = {
            "bot": bot,
            "query": message,
            "source": {
                "sourceType": "chat_input",
                "chatInputMetadata": {
                    "useVoiceRecord": False,
                    "newChatContext": "chat_settings_new_chat_button"
                }
            },
            "sdid": "",
            "attachments": []
        }
        response_json = self.send_request('gql_POST', 'ChatHelpersSendNewChatMessageMutation', variables)
        if response_json["data"] is None and response_json["errors"]:
            raise ValueError(
                f"Bot {bot} not found. Make sure the bot exists before creating new chat."
            )
        chatCode = response_json['data']['messageEdgeCreate']['chat']['chatCode']
        print(f'New Thread created | {chatCode}')
        return chatCode

    def send_message(self, bot: str, message: str, chatId: int = None, chatCode: str = None):
        print(f'Sending prompt using bot: {bot}')
        logging.info(f'Sending prompt using bot: {bot}')
        for i in range(MAX_RETRIES):
            try:
                if chatId is None:
                    chatCode = self.create_new_chat(bot, message)
                else:
                    chat_data = self.get_chat_history(bot=bot)[bot]
                    for chat in chat_data:
                        if chat['chatId'] == chatId and chatCode == None:
                            chatCode = chat['chatCode']
                            break
                        if chat['chatCode'] == chatCode and chatId == None:
                            chatId = chat['chatId']
                            break
                    variables = {'bot': bot, 'chatId': chatId, 'query': message,
                                 'source': {"sourceType": "chat_input", "chatInputMetadata": {"useVoiceRecord": False}},
                                 'withChatBreak': False, "clientNonce": generate_nonce(), 'sdid': "", 'attachments': []}
                    self.send_request('gql_POST', 'SendMessageMutation', variables)
                return self.get_latest_message(chatCode)['response'].strip()
            except Exception as e:
                print(f'An error occurred: {str(e)[:50]} \nSwitching account')
                if i < 2:
                    logging.error(f'An error occurred: {str(e)[:50]} \nSwitching account')
                self.__init__()

    def chat_break(self, bot: str, chatId: int = None, chatCode: str = None):
        chat_data = self.get_chat_history(bot=bot)[bot]
        chat_id = 0
        for chat in chat_data:
            if chat['chatId'] == chatId or chat['chatCode'] == chatCode:
                chatId = chat['chatId']
                chat_id = chat['id']
                break
        variables = {"connections": [
            f"client:{chat_id}:__ChatMessagesView_chat_messagesConnection_connection"],
            "chatId": chatId}
        self.send_request('gql_POST', 'chatHelpers_addMessageBreakEdgeMutation_Mutation', variables)

    def delete_message(self, message_ids):
        variables = {'messageIds': message_ids}
        self.send_request('gql_POST', 'DeleteMessageMutation', variables)

    def purge_conversation(self, bot: str, chatId: int = None, chatCode: str = None, count: int = 50):
        if chatId != None and chatCode == None:
            chatdata = self.get_chat_history(bot=bot)[bot]
            for chat in chatdata:
                if chat['chatId'] == chatId:
                    chatCode = chat['chatCode']
                    break
        variables = {'chatCode': chatCode}
        response_json = self.send_request('gql_POST', 'ChatPageQuery', variables)
        edges = response_json['data']['chatOfCode']['messagesConnection']['edges']

        num = count
        while True:
            if len(edges) == 0 or num == 0:
                break
            message_ids = []
            for edge in edges:
                message_ids.append(edge['node']['messageId'])
            self.delete_message(message_ids)
            num -= len(message_ids)
            if len(edges) < num:
                response_json = self.send_request('gql_POST', 'ChatPageQuery', variables)
                edges = response_json['data']['chatOfCode']['messagesConnection']['edges']

        print(f"Deleted {count - num} messages")

    def purge_all_conversations(self):
        print('Purging all conversations')
        logging.info('Purging all conversations')
        self.send_request('gql_POST', 'DeleteUserMessagesMutation', {})

    def get_latest_message(self, chatCode: str=""):
        variables = {'chatCode': chatCode}
        state = 'incomplete'
        while True:
            sleep(0.1)
            response_json = self.send_request('gql_POST','ChatPageQuery', variables)
            edges = response_json['data']['chatOfCode']['messagesConnection']['edges']
            chatId = response_json['data']['chatOfCode']['chatId']
            if edges:
                latest_message = edges[-1]['node']
                text = latest_message['text']
                state = latest_message['state']
                if state == 'complete':
                    break
            else:
                text = 'Fail to get a message. Please try again!'
                break
        return {"response": text, "chatId": chatId, "chatCode": chatCode}


# Example Usage:
''' 
                  LIST OF BOTS
    Assistant                        capybara
    Claude-instant-100k               a2_100k
    Claude-2-100k                        a2_2
    Claude-instant                         a2
    ChatGPT                        chinchilla
    ChatGPT-16k                        agouti  <-- currently not working
    GPT-4                              beaver  <-- currently not working
    GPT-4-32k                        vizcacha  <-- currently not working
    Google-PaLM                       acouchy
    Llama-2-7b                llama_2_7b_chat
    Llama-2-13b              llama_2_13b_chat
    Llama-2-70b              llama_2_70b_chat
    Code-Llama-7b      code_llama_7b_instruct
    Code-Llama-13b    code_llama_13b_instruct
    Code-Llama-34b    code_llama_34b_instruct
    Vicuna-13B-V13               vicuna13bv13
'''

if __name__ == "__main__":
    model = 'vicuna13bv13'
    message = """
    Hi
    """
    result = PoeApi().send_message(model, message)
    if result:
        print(result)
        print(f"success: {model}")
    else:
        print(f"failed: {model}")
