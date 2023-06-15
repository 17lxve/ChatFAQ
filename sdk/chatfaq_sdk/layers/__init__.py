from logging import getLogger
from typing import List

logger = getLogger(__name__)


class Layer:
    """
    Representation of all the future stack's layers. Implementing a new layer should inherit form this
    """

    _type = None

    def __init__(self, allow_feedback=True):
        self.allow_feedback = allow_feedback

    async def build_payloads(self, ctx, data) -> List[dict]:
        """
        Used to represent the layer as a dictionary which will be sent through the WS to the ChatFAQ's back-end server
        It is cached since there are layers as such as the LMGeneratedText which are computationally expensive
        :return:
            dict
                A json compatible dict
        """
        raise NotImplementedError

    async def dict_repr(self, ctx, data) -> List[dict]:
        repr_gen = self.build_payloads(ctx, data)
        async for _repr in repr_gen:
            for r in _repr:
                r["type"] = self._type
                r["meta"] = {}
                r["meta"]["allow_feedback"] = self.allow_feedback
            yield _repr


class Text(Layer):
    """
    Simplest layer representing raw text
    """

    _type = "text"

    def __init__(self, payload, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.payload = payload

    async def build_payloads(self, ctx, data):
        yield [{"payload": self.payload}]


class LMGeneratedText(Layer):
    """
    Layer representing text generated by a language model
    """

    _type = "lm_generated_text"
    loaded_model = {}

    def __init__(self, input_text, model_id, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_text = input_text
        self.model_id = model_id

    async def build_payloads(self, ctx, data):
        # model_response = ChatfaqRetrievalAPI(ctx.chatfaq_retrieval_http, ctx.token).query(self.model_id,
        #                                                                                   self.input_text)

        logger.debug(f"Waiting for LLM...")
        await ctx.send_llm_request(self.model_id, self.input_text, data["bot_channel_name"])

        logger.debug(f"...Receive LLM res")
        more = True
        while more:
            results, more = (await ctx.rpc_llm_request_futures[data["bot_channel_name"]])()
            for result in results:
                yield [{
                    "payload": {
                        "model_response": result["res"],
                        "finish": not more,
                        "references": [c["url"] for c in result["context"]],
                        "model": self.model_id
                    }
                }]
        logger.debug(f"LLM res Finished")
