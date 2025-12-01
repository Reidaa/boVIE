import click


class Choice(click.Choice):
    def __init__(self, choices, case_sensitive=False, ):
        super().__init__(choices, case_sensitive=case_sensitive)
        self.envvar_list_splitter = ","
