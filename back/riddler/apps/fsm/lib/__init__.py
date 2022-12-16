from typing import Coroutine, List, NamedTuple, Text

from asgiref.sync import sync_to_async

from riddler.apps.broker.models import Message


class State(NamedTuple):
    name: Text
    events: List[Text] = []
    initial: bool = False


class Transition(NamedTuple):
    source: Text
    dest: Text
    conditions: List[Text] = []
    unless: List[Text] = []


class SerializedMachine(NamedTuple):
    states: List[State]
    transitions: List[Transition]
    current_state: State = None


class MachineContext:
    def __init__(self, *args, **kargs):
        self.conversation_id = None
        self.fsm_name = None
        super().__init__(*args, **kargs)

    async def send_response(self, *args, **kargs):
        raise NotImplementedError(
            "All classes that behave as contexts for machines should implement 'send_response'"
        )

    def set_conversation_id(self, conversation_id):
        self.conversation_id = conversation_id

    def set_fsm_name(self, fsm_name):
        self.fsm_name = fsm_name

    async def get_last_mml(
        self,
    ) -> Message:  # TODO: property return type for a coroutine
        return await sync_to_async(
            Message.objects.filter(conversation=self.conversation_id)
            .order_by("-created_date")
            .first
        )()


class Machine:
    def __init__(
        self,
        ctx: MachineContext,
        states: List[State],
        transitions: List[Transition],
        current_state: State = None,
    ):
        self.ctx = ctx
        self.states = states
        self.transitions = transitions

        self.current_state = current_state
        if not current_state:
            self.current_state = self.get_initial_state()

    async def start(self):
        await self.run_current_state_events()
        await self.save_cache()

    async def next_state(self):
        transitions = self.get_current_state_transitions()
        for t in transitions:
            if await self.check_transition_condition(t):
                self.current_state = self.get_state_by_name(t.dest)
                await self.run_current_state_events()
                break
        await self.save_cache()

    async def run_current_state_events(self):
        for event in self.current_state.events:
            await getattr(self.ctx, event)()

    def get_initial_state(self):
        for state in self.states:
            if state.initial:
                return state
        raise Exception("There must be an initial state")

    def get_state_by_name(self, name):
        for state in self.states:
            if state.name == name:
                return state

    def get_current_state_transitions(self):
        return filter(lambda t: t.source == self.current_state.name, self.transitions)

    async def check_transition_condition(self, transition):
        for condition in transition.conditions:
            if not await getattr(self.ctx, condition)():
                return False

        for condition in transition.unless:
            if await getattr(self.ctx, condition)():
                return False

        return True

    async def save_cache(self):
        from riddler.apps.fsm.models import CachedMachine  # TODO: Resolve CI

        await sync_to_async(CachedMachine.update_or_create)(self)