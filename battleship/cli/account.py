from typing import Annotated, Any, Generator

from httpx import Client
from typer import Exit, Option, Typer

from battleship.cli.config import get_config
from battleship.cli.console import get_console

app = Typer()
console = get_console()


def _unpack_400_errors(errors: list[dict[str, Any]]) -> Generator[tuple[str, str], None, None]:
    for error in errors:
        fields = ", ".join(error["loc"])
        msg = error["msg"]
        yield fields, msg


@app.command()
def signup(
    email: Annotated[str, Option(prompt=True)],
    nickname: Annotated[str, Option(prompt=True)],
    password: Annotated[str, Option(prompt=True, confirmation_prompt=True, hide_input=True)],
) -> None:
    config = get_config()

    with console.status(f"Creating user {nickname}..."):
        creds = dict(email=email, nickname=nickname, password=password)

        with Client(base_url=str(config.SERVER_URL)) as client:
            response = client.post("/signup", json=creds)

        if response.status_code != 201:
            console.error(f"Cannot create this user. Error code {response.status_code}.")

            if response.status_code == 400:
                errors = response.json()

                for fields, msg in _unpack_400_errors(errors):
                    console.print(f"Fields: [accent]{fields}[/]. Reason: [accent]{msg}[/]")

            raise Exit(code=1)

    console.success(f"Signed up as {nickname}. Check your inbox for confirmation email.")
    console.print(
        "[b]Note: without confirmation you won't" " be able to restore access to your account![/]"
    )
