# ChatFAQ NLP Engine

This is the NLP Engine for ChatFAQ. It is divided in two modules:

1. Information Retrieval: This module is responsible for retrieving the most relevant answer to a given question.
2. Chatbot: This module is responsible for generating a response to the given question based on the retrieved answer and chat with the user.

# Information Retrieval

The `Retriever` is the main class for the information retrieval system. It takes as input a question (query) and a context and returns the most relevant sentences from the context to the query. This is done using embeddings and the dot product to compute the similarity between the query and the context sentences.


# Chatbot

## Prompt Generator

The `PromptGenerator` is the main class for generating the prompts.


## Chatbot

The `RetrieverAnswerer` is the main class for the chatbot. It takes as input a question (query) and a context and returns a response to the query. This is done by first retrieving the most relevant sentences from the context to the query and then generating a response based on the retrieved sentences.


# Publish package

### PYPI test

add repository to poetry config

    poetry config repositories.chatfaq-retrieval https://test.pypi.org/legacy/

get token from https://test.pypi.org/manage/account/token/

store token using

    poetry config pypi-token.chatfaq-retrieval pypi-YYYYYYYY

### PYPI production

get token from https://pypi.org/manage/account/token/

store token using

    poetry config pypi-token.chatfaq-retrieval pypi-XXXXXXXX

Each time you need to publish

Bump version

    poetry version prerelease

or

    poetry version patch

### Poetry Publish

To TestPyPi

    poetry publish -r chatfaq-retrieval

To PyPi

    poetry publish