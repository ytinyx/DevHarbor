import argparse
import asyncio
import sys
from pathlib import Path

# Keep imports independent of the caller's working directory; leave dotenv
# discovery to app.core.config so configuration loading stays unchanged.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))


async def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test GitHub repository access.")
    parser.add_argument("owner")
    parser.add_argument("repo")
    args = parser.parse_args()

    from app.services.github.client import GitHubClient

    data = await GitHubClient().get_repo(args.owner, args.repo)
    print({"full_name": data.get("full_name"), "default_branch": data.get("default_branch")})


if __name__ == "__main__":
    asyncio.run(main())
