class Logger:
    def error(text: str) -> None:
        print("\033[31m" + text + "\033[0m")

    def success(text: str) -> None:
        print("\033[92m" + text + "\033[0m")

    def warning(text: str) -> None:
            print("\033[33m" + text + "\033[0m")