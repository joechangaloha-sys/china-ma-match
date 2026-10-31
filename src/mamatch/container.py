"""CloudRun/container entry point: honour PORT and the platform's trusted proxy headers."""

import os
from copy import deepcopy

import uvicorn


def main() -> None:
    log_config = deepcopy(uvicorn.config.LOGGING_CONFIG)
    log_config['filters'] = {'sensitive_paths': {'()': 'mamatch.logging_security.SensitivePathFilter'}}
    log_config['handlers']['access']['filters'] = ['sensitive_paths']
    uvicorn.run(
        "mamatch.web.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        workers=1,
        log_config=log_config,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("MAMATCH_FORWARDED_ALLOW_IPS", "*"),
    )


if __name__ == "__main__":
    main()
