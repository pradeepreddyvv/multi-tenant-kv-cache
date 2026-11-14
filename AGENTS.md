# Working on this prototype

Read README.md and docs/LIMITATIONS.md before changing the experiments. Historical component results are not evidence that the cleaned launcher or an adaptive controller has passed a new live test.

Keep paths configurable and outputs out of Git. Never commit credentials, local configuration, model artifacts, raw chat exports or the private preservation archive. Preserve original raw experiment records when reanalyzing them.

Do not launch a GPU job merely to review or format code. Any live test must run in an authorized compute allocation. Run syntax/unit checks and saved-log regression analysis for code changes when appropriate. Clearly report whether validation was static, replayed from saved logs, or a fresh deployment.
