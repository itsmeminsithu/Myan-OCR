"""Cooperative per-request OCR time budget.

Tesseract is a subprocess with its own timeout. PDF rasterization is checked
between pages. Thread cancellation cannot forcibly interrupt a running native
PDF renderer; the container also needs memory and CPU limits.
"""
import contextvars
import os
import time

_DEADLINE = contextvars.ContextVar('ocr_job_deadline', default=None)
MAX_SECONDS = max(5, min(int(os.getenv('OCR_JOB_DEADLINE_SECONDS', '75')), 300))


def begin_job():
    return _DEADLINE.set(time.monotonic() + MAX_SECONDS)


def end_job(token):
    _DEADLINE.reset(token)


def remaining_seconds():
    deadline = _DEADLINE.get()
    if deadline is None:
        return float(MAX_SECONDS)
    return max(0.0, deadline - time.monotonic())


def check_budget():
    if remaining_seconds() < 0.25:
        raise TimeoutError('OCR processing deadline exceeded. Try fewer pages or Fast mode.')
