import time

from asgiref.sync import sync_to_async

from .models import AgentType
from .serializers import MessageSerializer
from riddler.common.consumers import BotConsumer
from riddler.apps.fsm.lib import MachineContext


class RiddlerConsumer(BotConsumer):
    def get_fsm_name(self):
        return self.scope["url_route"]["kwargs"]["fsm"]

    async def send_response(self, ctx: MachineContext, msg: str):
        await self.channel_layer.group_send(
            ctx.conversation_id, {"type": "response", "text": msg}
        )

    async def response(self, payload: dict):
        last_mml = await self.get_last_mml()

        serializer = MessageSerializer(
            data={
                "transmitter": {
                    "type": AgentType.bot.value,
                },
                "confidence": 1,
                "payload": payload,
                "conversation": self.conversation_id,
                "send_time": int(time.time() * 1000),
                "prev": last_mml.pk if last_mml else None
            }
        )
        await sync_to_async(serializer.is_valid)()
        await sync_to_async(serializer.save)()
        # Send message to WebSocket
        await self.send(payload["text"])