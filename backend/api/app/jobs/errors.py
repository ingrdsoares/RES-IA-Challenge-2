class JobDeferred(Exception):
    """A dependency is still pending; do not consume a failure attempt."""


class AssistantStageFailed(Exception):
    def __init__(self, stages, checkpoint):
        super().__init__("assistant_stage_failed")
        self.stages = stages
        self.checkpoint = checkpoint
