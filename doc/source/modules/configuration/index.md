# AI Configuration

After setting up the components, you will probably want to configure a model that you want to use for your chatbot. Typically the model will be used from the SDK, from a state within its FSM.

## The RAG Pipeline

The [RAG (Retrieval-Augmented Generation)](https://arxiv.org/abs/2005.11401) architecture is a workflow that combines a retriever and a generator. The retriever is used to retrieve the most relevant knowledge items from a knowledge base, and the generator is used to generate an answer from the retrieved knowledge items.

In ChatFAQ we choose to follow this pattern. Next we explain how to configure it.

We define 5 main components that are needed to configure a RAG pipeline:

- Knowledge Base
- Retriever
- Prompt
- Generation
- LLM
- RAG

ChatFAQ provide in its fixtures a default configuration for each of these components except for the Knowledge Base and the RAG Config. You can apply the fixtures by simply running the following command from the `back` directory:

```bash
make apply_fixtures
```

We also provide an example of each component here, so you can use it as a reference.

Currently all the relevant data/models can be accessed and modified from the Django admin panel ([http://localhost/back/admin/](http://localhost/back/admin/)) or from the CLI.


### Knowledge Base

The knowledge base is your source of truth.

It typically starts with a collection of documents (CSVs, PDFs or URLs) that the chatbot will use to answer questions.

Once a knowledge base is created, the system will parse your source document and generate the corresponding knowledge items.

Next we list the different properties that a of knowledge bases has.

- **lang**: The language of the knowledge base. It is used to tokenize the documents.
- **original_csv**: The CSV file.
- **original_pdf**: The PDF file.
- **original_url**: The URL.

<b> CSV parsing options</b>

- **csv_header**: Whether the CSV file has a header or not.
- **title_index_col**: The index of the column that contains the title of the knowledge item.
- **content_index_col**: The index of the column that contains the content of the knowledge item.
- **url_index_col**: The index of the column that contains the URL of the knowledge item.
- **section_index_col**: The index of the column that contains the section of the knowledge item.
- **role_index_col**: The index of the column that contains the role of the knowledge item.
- **page_number_index_col**: The index of the column that contains the page number of the knowledge item.

<b> PDF and URL parsing options</b>

- **strategy**: The strategy to use to parse the PDF files. Can be 'auto', 'fast', 'ocr' or 'high_res'. Default: 'fast'.
- **recursive**: Whether to recursively parse the URLs or not. Default: True.
- **splitter**: The splitter used to split the documents into chunks. It is used to generate the knowledge items. Can be 'sentences', 'words', 'tokens' and 'smart'. Default: 'sentences'.
- **chunk_size**: The number of tokens per chunk. It is used by the splitter to split the documents into chunks. Default: 128.
- **chunk_overlap**: The number of tokens that overlap between two chunks. Default: 16.

#### Recommendations

- The **strategy** to use depends on the time that you want to wait for the parsing process to finish and the quality of the parsing process. The strategies are ordered from fastest to slowest and from worst quality to best quality. The 'fast' strategy is the default one and it is the one that we recommend for most use cases, it only lasts a few seconds and it has a good quality. The 'high_res' strategy is the one with the best quality but it can last several minutes. For more information about the different strategies check [here](https://unstructured-io.github.io/unstructured/bricks/partition.html#partition-pdf).

- The **splitter** that we recommend is the 'sentences' one. It splits the documents into sentences and then it merges the sentences into chunks of approximately 'chunk_size' tokens. This is the best option for most use cases. The 'smart' splitter uses GPT-4 to split the documents into semantic meaningful chunks, this is **VERY EXPENSIVE** and can bump into OpenAI rate limits (will be optimized in the future).

- The **chunk_size** that we recommend is 128. This is the default value and it is the one that we recommend for most use cases, it is a good balance between retrieval quality and information density. If you want to increase the retrieval quality you can decrease this value, but it will decrease the information density of a chunk.

- The **chunk_overlap** is used when splitting with the 'words' or 'tokens' splitters. 16 or 32 is enough for not losing information between chunks.

#### CSV Structure

An example of a CSV for the Knowledge Base is the following:

| title | content | url | section | role |
| --- | --- | --- | --- | --- |
| Can ChatFAQ integrate with communication tools like Slack and Teams? | Yes, ChatFAQ can integrate with communication tools like Slack and Teams, enhancing your communication capabilities and enabling seamless interactions with your audience. | https://www.chatfaq.io/features/integrations | Features > Integrations | user |
| Can the ChatFAQ Widget be tailored to fit specific brand identities? | Absolutely, the ChatFAQ Widget can be fully branded to reflect your brand's uniqueness, including size, color, fonts, and logo. This ensures it aligns perfectly with your brand identity. | https://www.chatfaq.io/features/widget | Features > Widget | user |
| Does ChatFAQ offer a customized Natural Language Processing (NLP) engine? | Yes, ChatFAQ includes a specialized NLP/NLG engine that enhances the conversational capabilities of chatbots, making them more effective in understanding and responding to user queries. | https://github.com/ChatFAQ/ChatFAQ | GitHub > Documentation | user |
| Does ChatFAQ offer specific enterprise solutions? | Indeed, ChatFAQ is suitable for businesses and can be tailored to meet enterprise needs. It offers features and customization options suitable for businesses of all sizes. | https://github.com/ChatFAQ/ChatFAQ | GitHub > About | user |
| Does the ChatFAQ Widget support multiple languages? | Yes, the ChatFAQ Widget is multilingual, allowing businesses to communicate with a global customer base while maintaining service quality. | https://www.chatfaq.io/features/widget | Features > Widget | user |
| How can I customize the user interface of the ChatFAQ Widget? | The ChatFAQ Widget offers complete flexibility over UI aspects, including size, color, fonts, and logo, to align with your brand's uniqueness and cater to your audience's needs. | https://www.chatfaq.io/features/widget | Features > Widget | user |
| How can I expand my knowledge dataset with ChatFAQ? | You can expand your knowledge dataset with ChatFAQ by uploading your business content as CSV or PDF files. ChatFAQ will automatically generate utterances to enhance your knowledge dataset, improving the accuracy of the AI model. Even if you don't have existing Frequently Asked Questions, ChatFAQ can infer FAQs and prepare a training dataset covering your business context. | https://www.chatfaq.io/features/generative-ai | Features > Generative AI | user |
| ... | ... | ... | ... | ... |

### Retriever Config

The retriever is the component that will retrieve the most relevant knowledge items from the knowledge base.

The retriever is configured with the following properties:

- **name**: Just a name for the retriever.
- **model_name**: The name of the retriever model to use. It must be a HuggingFace repo id. Default: 'intfloat/e5-small-v2'.
- **batch_size**: The batch size to use for the retriever. Default: 1.
- **device**: The device to use for the retriever. It can be a CPU or a GPU. Default: 'cpu'.

We recommend setting the **model_name** to one of the [e5 family models](https://huggingface.co/intfloat). The retriever is developed with these models as the base, so it will work better with them. We suggest to use [intfloat/e5-small-v2](https://huggingface.co/intfloat/e5-small-v2) for English and [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small) for other languages.

For **batch_size** we recommend using 1 for CPU and for GPU as much as your GPU can handle. For personal use, batch size of 1 is enough, but for production use, you should use a higher batch size and a GPU.

For **device** we recommend using a GPU if you have one available. For personal use it is enough to use a CPU, but for production use, you should use a GPU.

An example of a retriever config is the following:

```json
{
    "name": "e5-retriever",
    "model_name": "intfloat/e5-small-v2",
    "batch_size": 1,
    "device": "cpu"
}
```


### LLM Config
The LLM is the component that defines the model that will generate the answer from the prompt.

The LLM is configured with the following properties:

- **name**: Just a name for the LLM.
- **llm_type**: The type of LLM to use. It can be 'OpenAI', 'Local GPU Model' (HuggingFace), 'Local CPU Model (ggml)' or a 'vLLM Client'. Default: 'Local GPU Model'.
- **llm_name**: The name of the LLM to use. It can be a HuggingFace repo id, an OpenAI model id, etc. Default: gpt2.
- **ggml_llm_filename**: The GGML filename of the model, if it is a GGML model.
- **model_config**: The huggingface model config of the model, needed for GGML models.
- **load_in_8bit**: Whether to load the model in 8bit or not, only for Local GPU HuggingFace models. Default: False.
- **use_fast_tokenizer**: Whether to use the fast tokenizer or not. Default: True.
- **trust_remote_code_tokenizer**: Whether to trust the remote code for the tokenizer or not. Default: False.
- **trust_remote_code_model**: Whether to trust the remote code for the model or not. Default: False.
- **revision**: The specific model version to use. It can be a branch name, a tag name, or a commit id, since we use a git-based system for storing models. Default: main.
- **model_max_length**: The maximum length of the model. Default: None.


Our preferred option is to use an open-source LLM like [Llama-2](https://huggingface.co/meta-llama/Llama-2-7b-chat-hf) for English and [Qwen-Chat](https://huggingface.co/Qwen/Qwen-7B-Chat) for other languages. 

To access Llama-2 models you need to set a environment variable in the back `.env` file with your HuggingFace API key:
```
HUGGINGFACE_KEY=XXXXXX
```


We can run these models locally, using a GPU or a CPU. 

#### GPU

For GPU we recommend using the following configuration:
```json
{
    "name": "Llama2_GPU",
    "llm_type": "Local GPU Model",
    "llm_name": "meta-llama/Llama-2-7b-chat-hf",
    "revision": "main",
    "load_in_8bit": false,
    "use_fast_tokenizer": true,
    "trust_remote_code_tokenizer": false,
    "trust_remote_code_model": false,
    "model_max_length": 4096
}
```
This uses the HuggingFace model implementations.

> ⚠️ To know if our GPU is enough to load the model we need to multiply its number of parameters by 2. For example, Llama-2-7B has 7B parameters, so we need at least 14GB of GPU memory to load it. This is because every parameter is stored in 2 bytes.


#### CPU

For CPU we recommend using the following configuration:
```json
{
    "name": "Llama2_CPU",
    "llm_type": "Local CPU Model (ggml)",
    "llm_name": "TheBloke/Llama-2-7B-GGML",
    "revision": "main",
    "ggml_llm_filename": "llama-2-7b.ggmlv3.q4_0.bin",
    "model_config": "meta-llama/Llama-2-7b-chat-hf",
    "use_fast_tokenizer": true,
    "trust_remote_code_tokenizer": false,
    "trust_remote_code_model": false,
    "model_max_length": 4096
}
```

This uses the [GGML](https://github.com/ggerganov/ggml/) library and [CTransformers](https://github.com/marella/ctransformers/tree/main) for python bindings. For a list of available models, check [here](https://github.com/marella/ctransformers/tree/main#supported-models).

For these configurations we need to specify the repo where the models files are stored (llm_name) and then the filename of the model file (ggml_llm_filename). We also need to specify the model config, which is the HuggingFace model config of the model.

> ⚠️ To know if our CPU is enough to run the model we need to divide its number of parameters by 2. For example, Llama-2-7B has 7B parameters, so we need at least 3.5GB of RAM to run it. This is because it uses 4 bit quantization and every parameter is stored in 4 bits.
>
> Given that our prompts are long, the time to get the first word can be long (several seconds), but after that the generation is fast.

#### OpenAI

This is the easiest way to get a model running. We just need to specify the model type and the model name. For example:
```json
{
    "name": "ChatGPT",
    "llm_type": "OpenAI",
    "llm_name": "gpt-3.5-turbo"
}
```

The OpenAI models are specified [here](https://platform.openai.com/docs/models/). `gpt-3.5-turbo` should be enough for most use cases. To access OpenAI models you need to set a environment variable in the back `.env` file with your OpenAI API key:
```
OPENAI_API_KEY=XXXXXX
```

#### vLLM Client

This uses a client to connect to a [vLLM server](https://github.com/vllm-project/vllm). The vLLM server is a server that runs a LLM model and exposes an API to generate answers, it has the best latency and throughput performance. 

To configure this server you need to:

- You need to specify the model that you want to use inside this [`Dockerfile`](https://github.com/ChatFAQ/ChatFAQ/tree/develop/model_engines/llm), and then follow [this instructions](https://github.com/ChatFAQ/ChatFAQ/tree/develop/model_engines/llm).
- - You need to specify the URL of the vLLM server in the `.env`. Usually it will be `VLLM_ENDPOINT_URL=http://localhost:5000/generate`.
- Start the back, go to the admin and from it you only need to specify that you want to use the `vLLM Client`.


### Prompt Config
The prompt is the input that the LLM will use to generate the answer. This config indicates how to build the final prompt that the LLM reads.

- **name**: Just a name for this prompt.
- **system_prefix**: This system prompt indicates the LLM how to behave.
- **system_tag**: The tag to indicate the start of the system prefix for the LLM.
- **system_end**: The tag to indicate the end of the system prefix for the LLM.
- **user_tag**: The tag to indicate the start of the user input.
- **user_end**: The tag to indicate the end of the user input.
- **assistant_tag**: The tag to indicate the start of the assistant output.
- **assistant_end**: The tag to indicate the end of the assistant output.
- **n_contexts_to_use**: The number of contexts from the Retriever to use in the generation process. Default: 3

We recommend using the [ChatML guidelines](https://github.com/openai/openai-python/blob/main/chatml.md), an of course using LLMs trained using this format, like Llama-2. The example here is the prompt format used by [Llama-2](https://huggingface.co/blog/llama2#how-to-prompt-llama-2):

In the system prefix you can use the following text behavior:
```
You are a helpful, respectful and honest assistant. Always answer as helpfully as possible, while being safe.  Your answers should not include any harmful, unethical, racist, sexist, toxic, dangerous, or illegal content. Please ensure that your responses are socially unbiased and positive in nature.

If a question does not make any sense, or is not factually coherent, explain why instead of answering something not correct. If you don't know the answer to a question, please don't share false information.
```

Then for the tags it is recommended to use the following:
```json
{
    "name": "Llama2_PromptConfig",
    "system_prefix": "You are a helpful, respectful and honest assistant. <Rest of the text> If you don't know the answer to a question, please don't share false information.\n\n",
    "system_tag": "<s>[INST] <<SYS>>\n",
    "system_end": "\n<</SYS>>\n",
    "user_tag": "",
    "user_end": "[/INST]\n",
    "assistant_tag": "",
    "assistant_end": "[/INST]\n"
}
```

When constructing the prompt we just concatenate the tags in the following order:
1. system_tag
2. system_prefix
3. system_end
4. user_tag
5. user message
6. user_end
7. assistant_tag
8. assistant output
9. assistant_end

For **n_contexts_to_use** a standard practice is to use 3.

> ⚠️ If you use an OpenAI model you only need to specify the **system prefix**, the other fields are not used.


### Generation Config
The generation config is used to define the characteristics of the second part from the RAG pipeline, the generation process. We use sampling to generate the answer.

The sampling generation process is configured with the following properties:

- **name**: Just a name for the generation process.
- **top_k**: The number of tokens to consider for the top-k sampling. Default: 50.
- **top_p**: The cumulative probability for the top-p sampling. Default: 1.0.
- **temperature**: The temperature for the sampling. Default: 0.2.
- **repetition_penalty**: The repetition penalty for the sampling. Default: 1.0.
- **seed**: The seed for the sampling. Default: 42.
- **max_new_tokens**: The maximum number of new tokens to generate. Default: 256.

We recommend setting the temperature to low values, less than 1.0 because we want the model to be factual, not creative. A very good guide of all this parameters can be found in the [HuggingFace documentation](https://huggingface.co/blog/how-to-generate).

An example of a generation config is the following:
```json
{
    "name": "Llama2_GenerationConfig",
    "top_k": 50,
    "top_p": 1.0,
    "temperature": 0.2,
    "repetition_penalty": 1.0,
    "seed": 42,
    "max_new_tokens": 256
}
```

### RAG Config
Finally, the RAG config is used to glue all the previous components together.

It relates the different elements to create a RAG (Retrieval Augmented Generation) pipeline.

The RAG config is configured with the following properties:

- name: Just a name for the RAG config.
- knowledge_base: The knowledge base to use.
- llm_config: The LLM config to use.
- prompt_config: The prompt config to use.
- generation_config: The generation config to use.
- retriever_config: The retriever config to use.

Remember that currently all the relevant data/models can be accessed and modified from the Django admin panel ([http://localhost/back/admin/](http://localhost/back/admin/)) or from the CLI.


An example of a RAG config is the following:
```json
{
    "name": "chatfaq_llama_rag",
    "knowledge_base": "ChatFAQ_KB",
    "llm_config": "Llama2_GPU",
    "prompt_config": "Llama2_PromptConfig",
    "generation_config": "Llama2_GenerationConfig",
    "retriever_config": "e5-retriever"
}
```

## Using your RAG Pipeline

To create the RAG pipeline you just need to link all the components together. You can do it from the Django admin panel ([http://localhost/back/admin/](http://localhost/back/admin/)).

Then, if you go to the Celery logs you will see that the RAG pipeline is being built. This process can take several minutes, depending on the size of the knowledge base. When it is finished you will see a message like this:
```
[2023-10-20 11:03:22,743: INFO/MainProcess] Loading RAG config: chatfaq_llama_rag with llm: meta-llama/Llama-2-7b-chat-hf with llm type: Local GPU Model with knowledge base: chatfaq retriever: intfloat/e5-small-v2 and retriever device: cpu
```


Once you have created your RAG pipeline, you can use it to generate answers.

The last step will be to reference the name of the Rag Config from a state of your SDK's FSM. <a href="/en/latest/modules/sdk/index.html#model-example">Here is an example of that</a>