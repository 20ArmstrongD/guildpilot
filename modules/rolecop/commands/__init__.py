from .promote import register_promote_command
from .demote import register_demote_command
from .kick import register_kick_command

__all__ = [
    "register_promote_command",
    "register_demote_command",
    "register_kick_command",
]
