import csv
from io import StringIO
from logging import getLogger

from django.db import models, transaction
from django.apps import apps

from back.apps.broker.models import RemoteSDKParsers
from back.apps.language_model.tasks import parse_pdf_task, parse_url_task, generate_embeddings_task
from back.common.models import ChangesMixin
from back.apps.broker.models.message import Message
from pgvector.django import VectorField

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from back.utils.celery import recache_models

logger = getLogger(__name__)


class KnowledgeBase(ChangesMixin):
    """
    A knowledge base groups all its knowledge items under one language and keeps the original file for reference.

    name: str
        Just a name for the knowledge base.
    original_csv: FileField
        The original CSV file.
    original_pdf: FileField
        The original PDF file.
    original_url: URLField
        The original URL.
    lang: en, es, fr
        The language of the knowledge base.
    """

    LANGUAGE_CHOICES = (
        ("en", "English"),
        ("es", "Spanish"),
        ("fr", "French"),
    )
    name = models.CharField(max_length=255, unique=True)

    STRATEGY_CHOICES = (
        ("auto", "Auto"),
        ("fast", "Fast"),
        ("ocr_only", "OCR Only"),
        ("hi_res", "Hi Res"),
    )

    SPLITTERS_CHOICES = (
        ("sentences", "Sentences"),
        ("words", "Words"),
        ("tokens", "Tokens"),
        ("smart", "Smart"),
    )

    lang = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default="en")
    # CSV parsing options
    csv_header = models.BooleanField(default=True)
    title_index_col = models.IntegerField(default=0)
    content_index_col = models.IntegerField(default=1)
    url_index_col = models.IntegerField(default=2)
    section_index_col = models.IntegerField(default=3)
    role_index_col = models.IntegerField(default=4)
    page_number_index_col = models.IntegerField(default=5)
    # PDF parsing options
    strategy = models.CharField(max_length=10, default="fast", choices=STRATEGY_CHOICES)
    # URL parsing options
    recursive = models.BooleanField(default=True)
    # PDF & URL parsing options
    splitter = models.CharField(max_length=10, default="sentences", choices=SPLITTERS_CHOICES)
    chunk_size = models.IntegerField(default=128)
    chunk_overlap = models.IntegerField(default=16)

    original_csv = models.FileField(blank=True, null=True)
    original_pdf = models.FileField(blank=True, null=True)
    original_url = models.URLField(blank=True, null=True)

    parser = models.CharField(max_length=255, null=True, blank=True)

    def update_items_with_remote_parser(self):
        KnowledgeItem.objects.filter(
            knowledge_base=self).delete()  # TODO: give the option to reset the dataset or not, if reset is True, pass the last date of the last item to the spider and delete them when the crawling finishes
        channel_layer = get_channel_layer()
        layer_name = RemoteSDKParsers.get_next_consumer_group_name(self.parser)
        if layer_name:
            async_to_sync(channel_layer.send)(
                layer_name,
                {
                    "type": "send_data_source_to_parse",
                    "parser": self.parser,
                    "payload": {
                        "kb_id": self.pk,
                        "data_source": self.original_csv or self.original_pdf or self.original_url
                    }
                }
            )
        else:
            logger.error(f"No parser available for {self.parser}")
            raise Exception(f"No parser available for {self.parser}")

    def update_items_from_csv(self):
        csv_content = self.original_csv.read().decode("utf-8")
        csv_rows = csv.reader(StringIO(csv_content))
        if self.csv_header:
            next(csv_rows)
        new_items = [
            KnowledgeItem(
                knowledge_base=self,
                title=row[self.title_index_col] if len(row) > self.title_index_col else "",
                content=row[self.content_index_col] if len(row) > self.content_index_col else "",
                url=row[self.url_index_col] if len(row) > self.url_index_col else "",
                section=row[self.section_index_col] if len(row) > self.section_index_col else "",
                role=row[self.role_index_col] if len(row) > self.role_index_col else "",
            )
            for row in csv_rows
        ]

        KnowledgeItem.objects.filter(knowledge_base=self).delete()  # TODO: give the option to reset the dataset or not, if reset is True, pass the last date of the last item to the spider and delete them when the crawling finishes
        KnowledgeItem.objects.bulk_create(new_items)
        self.trigger_generate_embeddings()

    def trigger_generate_embeddings(self):
        RAGConfig = apps.get_model("language_model", "RAGConfig")
        Embedding = apps.get_model("language_model", "Embedding")

        rag_configs = RAGConfig.objects.filter(knowledge_base=self)
        last_i = rag_configs.count() - 1
        for i, rag_config in enumerate(rag_configs.all()):
            # remove all existing embeddings for this rag config
            Embedding.objects.filter(rag_config=rag_config).delete()
            generate_embeddings_task.delay(
                list(self.knowledgeitem_set.values_list("pk", flat=True)),
                rag_config.pk,
                recache_models=(i == last_i),
            )

    def to_csv(self):
        items = KnowledgeItem.objects.filter(knowledge_base=self)
        f = StringIO()

        fieldnames = ["title", "content", "url", "section", "role", "page_number"]

        writer = csv.DictWriter(f, fieldnames=fieldnames, )
        writer.writeheader()

        for item in items:
            row = {
                "title": item.title if item.title else None,
                "content": item.content,
                "url": item.url if item.url else None,
                "section": item.section if item.section else None,
                "role": item.role if item.role else None,
                "page_number": item.page_number if item.page_number else None,
            }
            writer.writerow(row)

        return f.getvalue()

    def get_data(self):
        items = KnowledgeItem.objects.filter(knowledge_base=self)
        logger.info(f'Retrieving items from knowledge base "{self.name}')
        logger.info(f"Number of retrieved items: {len(items)}")
        result = {}
        for item in items:
            result.setdefault("title", []).append(item.title)
            result.setdefault("content", []).append(item.content)
            result.setdefault("url", []).append(item.url)
            result.setdefault("section", []).append(item.section)
            result.setdefault("role", []).append(item.role)
            result.setdefault("page_number", []).append(item.page_number)

        return result

    def __str__(self):
        return self.name or "Knowledge Base {}".format(self.id)

    def save(self, *args, **kw):
        super().save(*args, **kw)
        if self._should_update_items_from_file():
            self.update_items_from_file()

    def _should_update_items_from_file(self):
        if not self.pk:
            return True

        orig = KnowledgeBase.objects.get(pk=self.pk)
        return orig.original_csv != self.original_csv or orig.original_pdf != self.original_pdf or self.parser != orig.parser

    def update_items_from_file(self):
        if self.parser:
            logger.info("Updating items from remote SDK parser")
            self.update_items_with_remote_parser()
        if self.original_csv:
            logger.info("Updating items from CSV")
            self.update_items_from_csv()
        elif self.original_pdf:
            logger.info("Updating items from PDF")
            parse_pdf_task.delay(self.pk)
        elif self.original_url:
            logger.info("Updating items from URL")
            parse_url_task.delay(self.pk, self.original_url)


class KnowledgeItem(ChangesMixin):
    """
    An item is a question/answer pair.

    knowledge_base: KnowledgeBase
        The knowledge base it belongs to.
    title: str
        The question of the FAQ.
    content: str
        The answer to the FAQ.
    url: str
        The context of the FAQ, usually is the breadcrumb of the page where the FAQ is.
    section: str
        Sometimes the web pages have different user roles and it serves different FAQs to each one of them.
    role: str
        The URL of the page where the FAQ is.
    embedding: VectorField
        A computed embedding for the model.
    """

    knowledge_base = models.ForeignKey(KnowledgeBase, on_delete=models.CASCADE)
    title = models.TextField(blank=True, null=True)
    content = models.TextField()
    url = models.URLField(max_length=2083)
    section = models.TextField(blank=True, null=True)
    role = models.CharField(max_length=255, blank=True, null=True)
    page_number = models.IntegerField(blank=True, null=True)
    message = models.ManyToManyField(Message, through="MessageKnowledgeItem")

    def __str__(self):
        return f"{self.content} ds ({self.knowledge_base.pk})"

    # When saving we want to check if the content has changed and in that case regenerate
    # all the embeddings for the rag_config this item belongs to.
    def save(self, *args, **kwargs):
        generate_embeddings = False

        if self.pk is None:
            generate_embeddings = True
        else:
            old_item = KnowledgeItem.objects.get(pk=self.pk)
            if self.content != old_item.content:
                generate_embeddings = True

        super().save(*args, **kwargs)

        if generate_embeddings:
            def on_commit_callback():
                self.trigger_generate_embeddings()

            # Schedule the trigger_generate_embeddings function to be called
            # after the current transaction is committed
            transaction.on_commit(on_commit_callback)

    def trigger_generate_embeddings(self):
        RAGConfig = apps.get_model("language_model", "RAGConfig")
        Embedding = apps.get_model("language_model", "Embedding")
        rag_configs = RAGConfig.objects.filter(knowledge_base=self.knowledge_base)
        last_i = rag_configs.count() - 1

        for i, rag_config in enumerate(rag_configs.all()):
            # remove the embedding for this item for this rag config
            Embedding.objects.filter(rag_config=rag_config, knowledge_item=self).delete()
            generate_embeddings_task.delay(
                [self.pk],
                rag_config.pk,
                recache_models=(i == last_i),
            )


def delete_knowledge_items(knowledge_item_ids):
    # Custom batch delete function for KnowledgeItem that recaches the models once the batch delete is done
    with transaction.atomic():
        # Perform the batch delete
        KnowledgeItem.objects.filter(id__in=knowledge_item_ids).delete()

        # Log and perform post-delete actions
        logger.info(f"Deleted {len(knowledge_item_ids)} knowledge items")
        recache_models("on_ki_delete")


class Embedding(ChangesMixin):
    """
    Embedding representation for a KnowledgeItem.
    knowledge_item: KnowledgeItem
        The KnowledgeItem associated with this embedding.
    rag_config: RAGConfig
        The RAGConfig associated with this embedding.
    embedding: ArrayField
        The actual embedding values.
    """

    knowledge_item = models.ForeignKey(KnowledgeItem, on_delete=models.CASCADE)
    rag_config = models.ForeignKey("RAGConfig", on_delete=models.CASCADE)
    embedding = VectorField(null=True, blank=True)

    def __str__(self):
        return f"Embedding for {self.knowledge_item}"


class AutoGeneratedTitle(ChangesMixin):
    """
    An utterance is a synonym of an item.

    knowledge_item: KnowledgeItem
        The knowledge item this synonym refers to.
    title: str
        The synonym of the item.
    embedding: VectorField
        A computed embedding for the model.
    """

    knowledge_item = models.ForeignKey(KnowledgeItem, on_delete=models.CASCADE)
    title = models.TextField()
    embedding = VectorField(null=True, blank=True)


class Intent(ChangesMixin):
    """
    An intent is a group of utterances.

    name: str
        The name of the intent.
    auto_generated: bool
        If the intent was auto generated or not.
    valid: bool
        If the intent is validated by the admin or not.
    new_intent: bool
        If the intent is new, or if it exists already in the knowledge base.
    message: Message
        The message associated with this intent.
    """
    intent_name = models.CharField(max_length=255, unique=True)
    auto_generated = models.BooleanField(default=False)
    valid = models.BooleanField(default=False)
    suggested_intent = models.BooleanField(default=False)
    message = models.ManyToManyField(Message, blank=True)
    knowledge_item = models.ManyToManyField(KnowledgeItem, blank=True)
    # Maybe add a knowledge_base foreign key here for querying simplicity and performance


class MessageKnowledgeItem(ChangesMixin):
    """
    A message can have multiple knowledge items.

    message: Message
        The message associated with this knowledge item.
    knowledge_item: KnowledgeItem
        The knowledge item associated with this message.
    similarity: float
        The similarity between the message and the knowledge item.
    valid: bool
        If the relation is validated by the admin or not.
    """

    message = models.ForeignKey(Message, on_delete=models.CASCADE)
    knowledge_item = models.ForeignKey(KnowledgeItem, on_delete=models.CASCADE)
    similarity = models.FloatField(null=True, blank=True)
    valid = models.BooleanField(default=False)
