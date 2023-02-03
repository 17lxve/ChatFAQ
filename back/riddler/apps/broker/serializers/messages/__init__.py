from drf_spectacular.utils import extend_schema_serializer, OpenApiExample

from riddler.apps.broker.models.message import StackPayloadType, AgentType

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from riddler.common.abs.bot_consumers import BotConsumer
from riddler.common.serializer_fields import JSTimestampField
from riddler.common.validators import AtLeastNOf, PresentTogether
from io import StringIO
from lxml import etree

from logging import getLogger

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from riddler.apps.broker.models.message import Message

logger = getLogger(__name__)


class BotMessageSerializer(serializers.Serializer):
    def to_mml(self, ctx: BotConsumer) -> "Message":
        """
        It should convert the validated data (it's called after calling 'is_valid') coming from the platform to a MML
        structure.

        Parameters
        ----------
        ctx: BotConsumer
            current context of the consumer using this serializer, useful for accessing the conversation_id, platform_config, etc


        Returns
        -------
        Message
            Saved MML

        """
        raise NotImplementedError(
            "You should implement a 'to_mml' method that converts your platform into an MML internal message"
        )

    @staticmethod
    def to_platform(mml: "Message", ctx: BotConsumer) -> dict:
        """
        It should convert a MML coming from the FSM to the platform expected schema
        structure.

        Parameters
        ----------
        mml: Message
            FMS's message
        ctx: BotConsumer
            current context of the consumer using this serializer, useful for accessing the conversation_id, platform_config, etc

        Returns
        -------
        dict
            Payload to be sent to the platform

        """
        raise NotImplementedError(
            "You should implement a 'to_mml' method that converts your platform into an MML internal message"
        )


class AgentSerializer(serializers.Serializer):

    first_name = serializers.CharField(required=False, max_length=255)
    last_name = serializers.CharField(required=False, max_length=255)
    type = serializers.ChoiceField(choices=[n.value for n in AgentType])
    platform = serializers.CharField(required=False, max_length=255)

    class Meta:

        validators = [
            PresentTogether(fields=[{"type": AgentType.human.value}, "platform"])
        ]


class QuickReplySerializer(serializers.Serializer):
    text = serializers.CharField(required=False)
    id = serializers.CharField(max_length=255)
    meta = serializers.JSONField(required=False)


class Payload(serializers.Field):
    def to_representation(self, obj):
        return obj

    def to_internal_value(self, data):
        return data

class TextPayload(serializers.Serializer):
    payload = serializers.CharField()

class HTMLPayload(serializers.Serializer):
    @staticmethod
    def html_syntax_validator(value):
        try:
            etree.parse(StringIO(value), etree.HTMLParser(recover=False))
        except XMLSyntaxError:
            raise serializers.ValidationError('This field must be valid HTML.')

    payload = serializers.CharField(validators=[html_syntax_validator])

class ImagePayload(serializers.Serializer):
    payload = serializers.URLField()

class ImagePayload(serializers.Serializer):
    payload = serializers.URLField()

class SatisfactionPayload(serializers.Serializer):
    payload = Payload()

class QuickRepliesPayload(serializers.Serializer):
    payload = Payload()


@extend_schema_serializer(
    examples = [
         OpenApiExample(
            'Valid example 1',
            summary='short summary',
            description='longer description',
            value={
                'meta': {'top10': True},
            },
        ),
    ]
)
class MessageStackSerializer(serializers.Serializer):
    # TODO: Implement the corresponding validations over the 'payload' depending on the 'type'

    type = serializers.ChoiceField(
        choices=[n.value for n in StackPayloadType]
    )
    payload = Payload(required=False, allow_null=True)
    id = serializers.CharField(required=False, max_length=255)
    meta = serializers.JSONField(required=False)

    def validate(self, data):
        if data.get('type') == StackPayloadType.text.value:
            s = TextPayload(data=data)
        elif data.get('type') == StackPayloadType.html.value:
            s = HTMLPayload(data=data)
        elif data.get('type') == StackPayloadType.image.value:
            s = ImagePayload(data=data)
        elif data.get('type') == StackPayloadType.satisfaction.value:
            s = SatisfactionPayload(data=data)
        elif data.get('type') == StackPayloadType.quick_replies.value:
            s = QuickRepliesPayload(data=data)
        else:
            raise serializers.ValidationError(f'type not supported {data.get("type")}')
        s.is_valid(raise_exception=True)
        data["payload"] = s.validated_data["payload"]
        return data

    """
    satisfaction = serializers.ChoiceField(
        required=False, choices=[n.value for n in Satisfaction], allow_null=True
    )
    text = serializers.CharField(required=False)
    html = serializers.CharField(required=False)
    image = serializers.CharField(required=False)
    response_id = serializers.CharField(required=False)
    satisfaction = serializers.ChoiceField(
        required=False, choices=[n.value for n in Satisfaction], allow_null=True
    )
    meta = serializers.JSONField(required=False)
    quick_replies = QuickReplySerializer(required=False, many=True)
    """

    """
    class Meta:
        validators = [
            AtLeastNOf(
                fields=["text", "html", "image", "satisfaction", "quick_replies"],
                number=1,
            ),
            PresentTogether(fields=["response_id", "text"]),
        ]
    """


class MessageSerializer(serializers.ModelSerializer):
    stacks = serializers.ListField(child=serializers.ListField(child=MessageStackSerializer()))
    transmitter = AgentSerializer()
    receiver = AgentSerializer(required=False)
    send_time = JSTimestampField()

    class Meta:
        from riddler.apps.broker.models.message import Message  # TODO: CI
        model = Message
        fields = "__all__"

    def validate_prev(self, prev):
        """
        - There should be only one message with prev set to None
        - Prev should be None or belonging to the same conversation
        """
        from riddler.apps.broker.models.message import Message  # TODO: CI
        # It seems we are implementing "UniqueValidator" but nor really, because this will also fail for when value=None
        # and another message also already have value=None while UniqueValidator will not fail on this specific use case
        if Message.objects.filter(conversation=self.initial_data["conversation"], prev=prev).first():
            raise ValidationError(f"prev should be always unique for the same conversation")
        if prev and prev.conversation != str(self.initial_data["conversation"]):
            raise ValidationError(f"prev should belong to the same conversation")
