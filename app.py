import json
import os
import sys

import httpx
from dotenv import load_dotenv

# get secrets from .env
load_dotenv("./.env")
openrouter_secret = os.getenv("OPENROUTER_SECRET")

# message history container
message_history = []

# message history structure
"""
[
{role: user, content: Hi},
{role: assistant, content: How to help?},
{role: user, content: <prompt>}
]
"""


def exit_app(user_message):
    if user_message == "q":
        sys.exit()


def openrouter_client(user_prompt: str) -> str:
    """Sends message history to OpenRouter API and returns the text content of the response.

    Args:
        user_prompt (str): String containing the message from the user.

    Returns:
        str: Bare text of the LLM response.
    """
    api_url = "https://openrouter.ai/api/v1/chat/completions"
    llm_model = "openai/gpt-5.2"
    message_data = {"model": llm_model, "messages": message_history}
    response = httpx.post(
        url=api_url, headers={"Authorization": f"Bearer {openrouter_secret}"}, data=json.dumps(message_data)
    )

    decoded_response = response.json()

    decoded_response = decoded_response["choices"][0]["message"]["content"]

    if response.status_code >= 400:
        print(f"\nApp ran into an error. Status code {response.status_code}")
        sys.exit(1)

    return decoded_response


def coordinator() -> None:
    print("Welcm to ChatBot App!\n\n\n")
    while True:
        # take input from user
        prompt = input("User: ")

        # save prompt in container
        message_history.append({"role": "user", "content": prompt})

        # exit check
        exit_app(prompt)
        # llm inference
        llm_response = openrouter_client(prompt)

        # update message history
        message_history.append({"role": "assistant", "content": llm_response})

        print("AI: ", llm_response)


if __name__ == "__main__":
    coordinator()
