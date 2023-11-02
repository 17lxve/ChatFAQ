from typing import List
from logging import getLogger

import numpy as np
import pandas as pd
from tqdm import tqdm
import torch
import torch.nn.functional as F
from torch import Tensor
from transformers import AutoTokenizer, AutoModel

from chat_rag.inf_retrieval.embedding_models.base_model import BaseModel

logger = getLogger(__name__)


class E5Model(BaseModel):
    """
    Class for retrieving the context for a given query using embeddings.
    """

    def __init__(
        self,
        model_name: str = "intfloat/e5-small-v2",
        use_cpu: bool = False,
        huggingface_key: str = None,
    ):
        """
        Parameters
        ----------
        model_name : str, optional
            Name of the model to be used for encoding the context, by default 'intfloat/multilingual-e5-base'
        use_cpu : bool, optional
            Whether to use CPU for encoding, by default False
        huggingface_key : str, optional
            Huggingface key to be used for private models, by default None
        """

        self.device = "cuda" if (not use_cpu and torch.cuda.is_available()) else "cpu"

        logger.info(f"Using device {self.device}")
        logger.info(f"Loading model {model_name}")

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_name, token=huggingface_key
        )

        if model_name == "intfloat/e5-small-v2":
            self.tokenizer.model_max_length = 512  # Max length not defined on the tokenizer_config.json for the small model

        self.model = AutoModel.from_pretrained(
            model_name,
            token=huggingface_key,
        ).to(self.device)