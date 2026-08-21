"""Adapters for `InvitationDispatcherPort` (ADR-0049).

One adapter for now, and it writes a line to the log. That is not a placeholder standing in
for the real thing: until the identity provider's own invitation is created from here, the
act an admin takes in this console and the act that lets somebody through the door are two,
and the honest thing is to say so where an operator can read it rather than to imply an
email went out.
"""

import logging

from app.modules.identity.domain.invitation import Invitation

logger = logging.getLogger(__name__)


class LoggingInvitationDispatcher:
    """Records that an invitation is waiting, and delivers nothing."""

    def dispatch(self, invitation: Invitation) -> None:
        logger.info(
            "invitation pending for %s (role=%s, expires=%s) - it is redeemed at that "
            "address's first login; inviting them in the identity provider is still a "
            "separate act",
            invitation.email,
            invitation.role,
            invitation.expires_at.isoformat() if invitation.expires_at else "never",
        )
