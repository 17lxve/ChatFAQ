from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from riddler.apps.broker.models import Message
from riddler.apps.fsm.lib import Machine, MachineContext


class BotConsumer(
    AsyncJsonWebsocketConsumer, MachineContext
):
    from riddler.apps.broker.serializers import MessageSerializer  # TODO: resolve CI

    serializer_class = MessageSerializer

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.machine: Machine = None
        self.fsm_name: str = None

    def get_fsm_name(self):
        raise NotImplemented("Implement a method that gathers the fsm name")

    async def connect(self):
        self.machine = await self.initialize_machine()
        self.set_conversation_id(self.scope["url_route"]["kwargs"]["conversation"])
        # Join room group
        await self.channel_layer.group_add(self.conversation_id, self.channel_name)
        await self.accept()
        await self.machine.start()

    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(self.conversation_id, self.channel_name)

    async def initialize_machine(self):
        from riddler.apps.fsm.models import FiniteStateMachine  # TODO: fix CI

        self.fsm_name = self.get_fsm_name()
        fsm = await sync_to_async(FiniteStateMachine.objects.get)(name=self.fsm_name)
        return fsm.build_machine(self)

    async def receive_json(self, *args):
        serializer = self.serializer_class(data=args[0])
        if not await sync_to_async(serializer.is_valid)():
            await self.channel_layer.group_send(
                self.conversation_id, {"type": "response", "errors": serializer.errors}
            )
        else:
            await sync_to_async(serializer.save)()
            await self.machine.next_state()