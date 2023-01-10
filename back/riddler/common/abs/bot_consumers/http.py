import json

from logging import getLogger

from asgiref.sync import sync_to_async

from channels.generic.http import AsyncHttpConsumer

from riddler.apps.fsm.models import CachedFSM
from riddler.common.abs.bot_consumers import BotConsumer

logger = getLogger(__name__)


class HTTPBotConsumer(BotConsumer, AsyncHttpConsumer):
    """
    Abstract class all HTTP bot consumers should inherit from,
    it takes care of the initialization and management of the fsm and
    the persistence of the sending/receiving MMLs into the database
    """

    async def resolve_fsm(self):
        """
        It will try to get a cached FSM from a provided name or create a new one in case
        there is no one yet (when is a brand-new conversation_id)
        Returns
        -------
        bool
            Whether or not it was able to create (new) or retrieve (cached) a FSM.
            If returns False most likely it is going be because a wrongly provided FSM name
        """
        self.fsm = await sync_to_async(CachedFSM.build_fsm)(self)
        if self.fsm:
            logger.debug(
                f"Continuing conversation ({self.conversation_id}), reusing cached conversation's FSM ({await sync_to_async(CachedFSM.get_conv_updated_date)(self)})"
            )
            await self.fsm.next_state()
        else:
            if self.platform_config is None:
                return False
            logger.debug(
                f"Starting new conversation ({self.conversation_id}), creating new FSM"
            )
            self.fsm = self.platform_config.fsm_def.build_fsm(self)
            await self.fsm.start()

        return True

    async def handle(self, body):
        """
        Entry point for the message coming from the platform, here we will serialize such message,
        store it in the database and call the FSM
        """

        await self.send_headers(headers=[
            (b"Content-Type", b"application/json"),
        ])
        data = json.loads(body.decode("utf-8"))
        serializer = self.serializer_class(data=data)
        if not serializer.is_valid():
            await self.send_json(serializer.errors)
        else:
            # with transaction.atomic():
            mml = serializer.to_mml()
            self.set_conversation_id(mml.conversation)
            self.set_platform_config(self.gather_platform_config(data))
            await self.channel_layer.group_add(self.get_group_name(), self.channel_name)

            await self.resolve_fsm()
            await self.send_json({"ok": "POST request processed"})

    async def send_json(self, data, more_body=False):
        await self.send_body(json.dumps(data).encode("utf-8"), more_body=more_body)
