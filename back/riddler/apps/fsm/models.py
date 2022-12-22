from typing import List

from django.db import models
from django_better_admin_arrayfield.models.fields import ArrayField
from typefit import typefit

from riddler.common.models import ChangesMixin

from .lib import FSM, FSMContext, State, Transition
from ...utils.logging_formatters import TIMESTAMP_FORMAT


class FSMDefinition(ChangesMixin):
    # TODO: Model 'definitions' inside DB ???
    name = models.CharField(null=True, unique=True, max_length=255)
    definition = models.JSONField(null=True)
    funcs = ArrayField(models.TextField(), default=list)

    def build_fsm(self, ctx: FSMContext, current_state: State = None) -> FSM:
        m = FSM(
            ctx=ctx,
            states=self.states,
            transitions=self.transitions,
            current_state=current_state,
        )
        self.declare_ctx_functions(ctx)
        return m

    def declare_ctx_functions(self, ctx: FSMContext):
        for f in self.funcs:
            loc = {}
            exec(f, globals(), loc)
            setattr(ctx, list(loc.keys())[0], list(loc.values())[0].__get__(ctx))

    @property
    def states(self) -> List[State]:
        return typefit(List[State], self.definition.get("states", []))

    @property
    def transitions(self) -> List[Transition]:
        return typefit(List[Transition], self.definition.get("transitions", []))


class CachedFSM(ChangesMixin):
    conversation_id = models.CharField(unique=True, max_length=255)
    current_state = models.JSONField(default=dict)
    fsm_def = models.ForeignKey(FSMDefinition, on_delete=models.CASCADE)

    @classmethod
    def update_or_create(cls, m: FSM):
        instance = cls.objects.filter(conversation_id=m.ctx.conversation_id).first()
        if instance:
            instance.current_state = m.current_state._asdict()
        else:
            fsm = FSMDefinition.objects.get(name=m.ctx.fsm_name)
            instance = cls(
                conversation_id=m.ctx.conversation_id,
                current_state=m.current_state._asdict(),
                fsm=fsm,
            )
        instance.save()

    @classmethod
    def build_fsm(cls, ctx: FSMContext) -> FSM:
        instance = cls.objects.filter(conversation_id=ctx.conversation_id).first()
        if instance:
            return instance.fsm_def.build_fsm(
                ctx, typefit(State, instance.current_state)
            )

        return None

    @classmethod
    def get_conv_updated_date(cls, ctx: FSMContext):
        instance = cls.objects.filter(conversation_id=ctx.conversation_id).first()
        if instance:
            instance.updated_date.strftime(TIMESTAMP_FORMAT)
