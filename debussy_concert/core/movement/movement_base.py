from typing import Protocol, Sequence
import inject
from debussy_concert.core.config.config_composition import ConfigComposition
from debussy_concert.core.entities.protocols import PMovementGroup
from debussy_concert.core.phrase.phrase_base import PPhrase
from debussy_concert.core.service.workflow.protocol import PWorkflowService


class PMovement(Protocol):
    name: str
    phrases: Sequence[PPhrase]
    workflow_service: PWorkflowService

    def play(self, *args, **kwargs):
        pass

    def build(self, dag) -> PMovementGroup:
        pass


class MovementBase(PMovement):
    @inject.params(config=ConfigComposition, workflow_service=PWorkflowService)
    def __init__(
        self,
        *,
        config: ConfigComposition,
        workflow_service: PWorkflowService,
        phrases: Sequence[PPhrase],
        name=None
    ) -> None:
        self.name = name or self.__class__.__name__
        self.config = config
        self.phrases = phrases
        self.workflow_service = workflow_service

    def play(self, *args, **kwargs):
        return self.build(*args, **kwargs)

    def build(self, workflow_dag) -> PMovementGroup:
        movement_group = self.workflow_service.movement_group(
            group_id=self.name, workflow_dag=workflow_dag
        )
        current_task_group = self.phrases[0].build(workflow_dag, movement_group)

        for phrase in self.phrases[1:]:
            phrase_task_group = phrase.build(workflow_dag, movement_group)
            current_task_group >> phrase_task_group
            current_task_group = phrase_task_group
        return movement_group
