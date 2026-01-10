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
    right_answers: List[str] = Field(default_factory=list)
    hints_used: List[str] = Field(default_factory=list)
    task_index: int


class HintOut(BaseModel):
    type: str = 'hint_use'
    hint_code: str
    hint_data: dict[str, Any] = Field(default_factory=dict)
    hints_use_amount: int
    id: Optional[str] = None
    last_hint: Optional[str] = None


class ResultsOut(BaseModel):
    type: str = 'results_send'
    results: dict[str, Any]
