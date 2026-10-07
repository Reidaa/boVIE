import click


class Choice(click.Choice):
    envvar_list_splitter = ","

    def __init__(
        self,
        choices,
        case_sensitive=False,
    ):
        super().__init__(choices, case_sensitive=case_sensitive)
