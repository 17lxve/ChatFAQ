import json
import time

from asgiref.sync import sync_to_async

from riddler.apps.fsm.lib import FSMContext
from riddler.common.abs.bot_consumers.ws import WSBotConsumer

from ..models.message import AgentType
from ..serializers.message import MessageSerializer
from riddler.utils import WSStatusCodes


class ExampleBotConsumer(WSBotConsumer):
    """
    A very simple implementation of the AbsBotConsumer just to show how could a Riddler bot work
    """
    from riddler.apps.broker.serializers.message import MessageSerializer  # TODO: resolve CI

    serializer_class = MessageSerializer

    def gather_platform_config(self):
        from ..models.platform_config import PlatformConfig  # TODO: Fix CI
        pk = self.scope["url_route"]["kwargs"]["pc_id"]
        return PlatformConfig.objects.select_related("fsm_def").get(pk=pk)

    def gather_conversation_id(self):
        return self.scope["url_route"]["kwargs"]["conversation"]

    async def send_response(self, ctx: FSMContext, msg: str):
        await self.channel_layer.group_send(
            self.get_group_name(), {"type": "response", "status": WSStatusCodes.ok.value, "payload": msg}
        )

    async def response(self, data: dict):
        if not WSStatusCodes.is_ok(data["status"]):
            await self.send(json.dumps(data))

        last_mml = await self.get_last_mml()
        serializer = MessageSerializer(
            data={
                "transmitter": {
                    "type": AgentType.bot.value,
                },
                "confidence": 1,
                "stacks": [[{
                    "type": "text",
                    "payload": data["payload"],
                }]],
                "conversation": self.conversation_id,
                "send_time": int(time.time() * 1000),
                "prev": last_mml.pk if last_mml else None,
            }
        )
        await sync_to_async(serializer.is_valid)()
        await sync_to_async(serializer.save)()
        # Send message to WebSocket
        await self.send(json.dumps({**serializer.data, "status": data["status"]}))
