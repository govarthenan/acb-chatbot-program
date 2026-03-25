import base64
import json
import os
import sys
from urllib.parse import urlparse

import chromadb
import httpx
import magic
from dotenv import load_dotenv

# get secrets from .env
load_dotenv("./.env")
openrouter_secret = os.getenv("OPENROUTER_SECRET")

# message history container
message_history: list[dict[str, str]] = []

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
current_file_types: list[str] = []
image_file_indicator = False


def is_remote_path(file_path: str) -> bool:
    """Differentiate whether a given file path is remote(internet) or local.

    Args:
        file_path (str): The file path given by the user during prompt input

    Returns:
        bool: True if local, False if remote.
    """
    result = urlparse(file_path)
    return all([result.scheme, result.netloc])


def get_file_mime_type(file_path: str) -> str:
    mime_type = magic.from_file(file_path, mime=True)
    return mime_type


def preprocessor_txt(txt_file_path: str) -> str:
    with open(file=txt_file_path, mode="r") as f:
        content = f.read()

    return content


def preprocessor_image(image_file_path: str, image_mime: str) -> str:
    data_url = f"data:{image_mime};base64,"

    with open(image_file_path, "rb") as f:
        image_data = f.read()

    decoded_base64 = base64.b64encode(image_data).decode()

    return data_url + decoded_base64


def files_handler(file_list: list[str]) -> dict[str, list[str]]:
    global image_file_indicator

    file_contents: dict[str, list[str]] = {}

    # mime type lists
    image_mime_types: list[str] = ["image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml"]

    # differentiate local and remote paths
    # for i in file_list:
    #     if is_local_path(i):
    #         local_files.append(i)
    #     else:
    #         remote_files.append(i)

    # check if given files exist
    for current_path in file_upload_paths:
        if not is_remote_path(current_path):
            if os.path.isfile(path=current_path):
                file_mime = get_file_mime_type(current_path)

                # knwon filetypes: txt
                if file_mime == "text/plain":
                    current_text_content: str = preprocessor_txt(current_path)
                    # check if file is empty
                    if len(current_text_content) == 0:
                        print(f"\nWARN: File {current_path} is empty!")
                        continue
                    file_contents[current_path] = [current_text_content, "text"]
                    current_file_types.append("text")

                elif file_mime in image_mime_types:
                    current_image_content = preprocessor_image(current_path, image_mime=file_mime)
                    file_contents[current_path] = [current_image_content, "image"]
                    # check if file is empty
                    if len(current_image_content) == 0:
                        print(f"\nWARN: File {current_path} is empty!")
                        continue
                    current_file_types.append("image")
                    image_file_indicator = True
                else:
                    print(f"\nWARN: File type {file_mime} not supported!\n")
            else:
                print(f"\nWARN: File {current_path} not found!\n")
        else:
            ...  # TODO: remote file fetching

    return file_contents


def file_content_prompt_generator(file_contents: dict[str, list[str]]) -> str:
    prompt_starter = f"The user has uploaded the following file types: {','.join(current_file_types)}. Please find the contents attached..."

    # append text files
    for key, val in file_contents.items():
        if val[1] == "text":
            prompt_starter: str = prompt_starter + f"\n\nFile: {key}" + f"\n```\n{val[0]}\n```\n"

    prompt_starter = prompt_starter + "---\n"

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


def knowledge_retrieval(vectordb: chromadb.Collection, prompt: str) -> str:
    # retrieve relevant chunks from vector DB
    results = vectordb.query(query_texts=[prompt], n_results=5)

    text_results = repr(results["documents"])

    return "Results from RAG:\n" + text_results + "\n" + prompt


def session_manager(vectordb: chromadb.Collection) -> None:
    global image_file_indicator

    print("Welcm to ChatBot App!\n\n\n")
    while True:
        # take input from user
        prompt = input("User: ")

        # RAG
        prompt = knowledge_retrieval(vectordb, prompt)

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
        # save prompt in container
        if image_file_indicator:
            for key, val in file_contents.items():
                if "image" in val:
                    message_history.append(
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {"type": "image_url", "image_url": {"url": val[0]}},
                            ],
                        }
                    )
        else:
            message_history.append({"role": "user", "content": prompt})

        # exit check
        exit_app(prompt)
        # llm inference
        llm_response = openrouter_client(prompt)

        # update message history
        message_history.append({"role": "assistant", "content": llm_response})

        print("AI: ", llm_response)

        # clear file upload queue
        file_upload_paths.clear()
        current_file_types.clear()
        image_file_indicator = False


def vectordb_initializer() -> chromadb.Collection:
    rag_client = chromadb.Client()
    collection = rag_client.create_collection("embedding_model_data")

    datadir = "data/text/"
    files: list[str] = os.listdir(datadir)
    file_paths = []

    for i in files:
        file_paths.append(datadir + i)

    file_contents = []

    for i in file_paths:
        current_file_pointer = open(i, "r")
        file_contents.append(current_file_pointer.read())

    # chunking
    chunks = []

    for file in file_contents:
        content = file
        content = content.split()

        current_chunks = []

        chunk_size = 50
        for i, w in enumerate(content):
            if i != 0:
                if i % chunk_size == 0:
                    chunk = content[i - chunk_size : i]
                    current_chunks.append(chunk)

        # calculate missed words and add them as a chunk
        included_words_count: int = len(current_chunks) * chunk_size
        missed_chunk = content[included_words_count : len(content) - 1]
        current_chunks.append(missed_chunk)

        chunks.extend(current_chunks)

    documents = []

    for i in chunks:
        documents.append(" ".join(i))

    file_ids = []
    for i in range(0, len(documents)):
        file_ids.append("id_" + str(i))

    # add contents to collection
    collection.add(ids=file_ids, documents=documents)

    return collection


if __name__ == "__main__":
    vectordb_collection = vectordb_initializer()
    session_manager(vectordb_collection)
