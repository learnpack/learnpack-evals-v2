"""Refusals shared by identity's roster acts.

Two of them are properties of the *target* rather than of the act — it does not exist, or it
is not the kind of assessor a roster can decide anything about — so granting a role and
withdrawing somebody refuse for the same reason and must say so with the same exception.
Duplicating them per use case is how two identical rules drift into two different sentences.
"""


class AssessorNotFound(Exception): ...


class NotAHumanAssessor(Exception):
    """An automated assessor is not on the roster in this sense: it is an artifact declared
    in code, and what it may do is decided by ratification against an instrument version
    (ADR-0019), not by a role and not by a status.
    """
