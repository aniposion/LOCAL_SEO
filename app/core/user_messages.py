"""Shared user-facing message helpers for unavailable integrations and failed workflows."""


def integration_unavailable(subject: str, dependency: str, next_step: str) -> str:
    """Build a consistent, actionable integration-unavailable message."""
    subject_text = subject.rstrip(".")
    dependency_text = dependency.rstrip(".")
    next_step_text = next_step.rstrip(".")
    return f"{subject_text} is unavailable right now because {dependency_text}. {next_step_text}."


def workflow_failed(subject: str, next_step: str) -> str:
    """Build a consistent, actionable workflow-failed message."""
    subject_text = subject.rstrip(".")
    next_step_text = next_step.rstrip(".")
    return f"{subject_text} failed. {next_step_text}."
