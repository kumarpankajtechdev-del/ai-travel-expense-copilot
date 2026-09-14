import argparse

import uvicorn


def main():
    parser = argparse.ArgumentParser(description="Run TripLedger locally.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--host",
        choices=["127.0.0.1", "0.0.0.0"],
        default="127.0.0.1",
        help="Use 0.0.0.0 only inside the provided local Docker setup.",
    )
    args = parser.parse_args()
    uvicorn.run("expense_ai_copilot.main:create_app", factory=True, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
