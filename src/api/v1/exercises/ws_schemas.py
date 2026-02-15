"""Websocket schemas for exercises sessions."""

from __future__ import annotations

from typing import List, Optional, Any
from pydantic import BaseModel, Field


class WsInitOut(BaseModel):
    type: str = 'init_info'
    total_tasks: int
    current_task: int


class TaskVariant(BaseModel):
    text: str


class TaskOut(BaseModel):
    type: str = 'task_send'
    task: dict[str, Any]
    total_tasks: int
    current_task: int


class VerdictOut(BaseModel):
    type: str = 'verdict'
    verdict: str
    corrects_amount: int
    incorrects_amount: int
    semi_corrects_amount: int
    right_answers_list: List[str] = Field(default_factory=list)
    hints_used: List[str] = Field(default_factory=list)
    # Stringified seconds for this answer, matching DRF get_verdict_data
    answer_time: str
    task_index: int


class HintOut(BaseModel):
    type: str = 'hint_use'
    hint_code: str
    hint_data: dict[str, Any] = Field(default_factory=dict)
    # When hints are unlimited, this is null; otherwise a non‑negative counter.
    hints_use_amount: Optional[int] = None
    id: Optional[str] = None
    # DRF/frontend treat this as a boolean flag; use bool here as well.
    last_hint: Optional[bool] = None


class ResultsOut(BaseModel):
    type: str = 'results_send'
    results: dict[str, Any]
