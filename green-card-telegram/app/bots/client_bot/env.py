import logging
import os

logger = logging.getLogger(__name__)


def resolve_env_value(
    primary_env: str, fallback_envs: tuple[str, ...] = (), default: str = ""
) -> str:
    """Return the first non-empty environment value from primary and fallback names."""
    for env_name in (primary_env, *fallback_envs):
        value = os.getenv(env_name)
        if value:
            if env_name != primary_env:
                logger.warning("Using %s as fallback for %s", env_name, primary_env)
            return value
    return default


def bitrix_webhook_fallback_envs(bitrix_webhook_env: str) -> tuple[str, ...]:
    """Support common EuroPolis Bitrix variable aliases without breaking defaults."""
    fallback_envs: list[str] = []
    if bitrix_webhook_env == "EUROPOLIS_BITRIX24_WEBHOOK_URL":
        fallback_envs.extend(
            [
                "EUROPOLIS_BITRIX_WEBHOOK_URL",
                "EUROPOLIS_BITRIX24_URL",
                "EUROPOLIS_BITRIX_URL",
                "BITRIX24_EUROPOLIS_WEBHOOK_URL",
                "BITRIX_EUROPOLIS_WEBHOOK_URL",
            ]
        )
    fallback_envs.append("BITRIX24_WEBHOOK_URL")
    return tuple(dict.fromkeys(env for env in fallback_envs if env != bitrix_webhook_env))
