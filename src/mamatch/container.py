"""CloudRun/container entry point: honour PORT and the platform's trusted proxy headers."""

import os

import uvicorn


def main() -> None:
    uvicorn.run(
        "mamatch.web.app:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        workers=1,
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("MAMATCH_FORWARDED_ALLOW_IPS", "*"),
    )


if __name__ == "__main__":
    main()
