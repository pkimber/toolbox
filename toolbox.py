import click


CYAN = 'cyan'
YELLOW = 'yellow'
WHITE = 'white'


@click.command()
def cli():
    click.clear()
    click.secho('Hello Greg', fg=WHITE, bold=True)
    click.echo()
    click.secho('Do you like running?', fg=YELLOW, bold=True)
    click.echo()
    click.secho(
        (
            'For more information, see: '
            'http://click.pocoo.org/3/quickstart/#screencast-and-examples'
        ),
        fg=CYAN
    )
    click.echo()


if __name__ == '__main__':
    cli()
