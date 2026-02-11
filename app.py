import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# get secrets from .env
load_dotenv("./.env")
openrouter_secret = os.getenv("OPENROUTER_SECRET")

# message history container
message_history: list[dict[str:str]] = []

# message history structure
"""
[
{role: user, content: Hi},
{role: assistant, content: How to help?},
{role: user, content: <prompt>}
]
"""

# list of files to be uploaded, refreshed at each turn of the conversation
file_upload_paths: list[str] = []


def preprocessor_txt(txt_file_path: str) -> str:
    with open(file=txt_file_path, mode="r") as f:
        content = f.read()

    return content


def files_handler(file_list: list[str]) -> dict[str:str]:
    file_contents: dict[str:str] = {}

    # check if given files exist
    for current_path in file_list:
        if os.path.isfile(path=current_path):
            file_type = Path(current_path).suffix

            # knwon filetypes: txt
            if file_type == ".txt":
                current_file_content: str = preprocessor_txt(current_path)
                # check if file is empty
                if len(current_file_content) == 0:
                    print(f"\nWARN: File {current_path} is empty!")
                    continue
                file_contents[current_path] = current_file_content
            else:
                print(f"\nWARN: File type {file_type} not supported!\n")
        else:
            print(f"\nWARN: File {current_path} not found!\n")

    return file_contents


def file_content_prompt_generator(file_contents: dict[str:str]) -> str:
    prompt_starter = "The user has uploaded some files. Here are the contents..."

    for key, val in file_contents.items():
        prompt_starter: str = prompt_starter + f"\n\nFile: {key}" + f"\n```\n{val}\n```\n"

    prompt_starter = "---"

    return prompt_starter


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


def session_manager() -> None:
    print("Welcm to ChatBot App!\n\n\n")
    while True:
        # take input from user
        prompt = input("User: ")

        # get file paths from user
        while True:
            _file_path = input("Location of file to upload: ")
            if _file_path == "":
                break
            else:
                file_upload_paths.append(_file_path)

        # handover processing of files to files_hander function
        file_contents = files_handler(file_upload_paths)

        if len(file_contents) > 0:
            file_prompt_prefix = file_content_prompt_generator(file_contents=file_contents)
            prompt = file_prompt_prefix + prompt

        print(file_contents)
        print(prompt)
        os._exit(0)

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
    session_manager()
