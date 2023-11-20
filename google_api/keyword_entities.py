import os
from google.cloud import language_v2
from scriptsv2.utils.usable_function import UsableFunc

cred_path = UsableFunc.paths('service_account')


def analyze_entity(keyword):
    """
    Analyzes Entities in a string.

    Args:
      keyword: The keyword or phrase to analyze

    Return:
      entity type for the given keyword
    """

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = cred_path
    client = language_v2.LanguageServiceClient()
    document = {
        "content": keyword,
        "type_": language_v2.Document.Type.PLAIN_TEXT,
        "language_code": "en",
    }

    response = client.analyze_entities(
        request={
            "document": document,
            "encoding_type": language_v2.EncodingType.UTF8
        }
    )

    return language_v2.Entity.Type(response.entities[0].type_).name


if __name__ == "__main__":
    entity_type = analyze_entity('create ai')
    print(entity_type)