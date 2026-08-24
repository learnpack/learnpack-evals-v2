"""Refusals shared by the registry's acts on an already-registered content.

`ContentNotFound` is a property of the **target**, not of the act: attributing a generator
(ADR-0024) and declaring a deployment (ADR-0054) refuse for the same reason and must say so
with the same exception. Defining it per use case is worse than untidy — `except` matches the
class and not the name, so a second class with this name is caught by nobody and the refusal
leaves as a 500. That is not hypothetical: it happened while ADR-0054's act was being written,
and `test_an_exception_name_means_one_thing_within_a_module` exists because of it.

Shared refusals only. An exception that belongs to one act stays in the file of that act.
"""


class ContentNotFound(Exception):
    """No content version with that id."""
