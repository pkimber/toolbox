import click
import subprocess

from lib.dev.folder import get_pillar_folder
from lib.server.name import (
    get_server_name_live,
    get_server_name_test,
)
from lib.site.info import SiteInfo

CYAN = 'cyan'
YELLOW = 'yellow'
WHITE = 'white'


@click.command()
@click.option('-s', '--site-name', prompt=True)
@click.option('--live/--test', default=False)
@click.option('--op', type=click.Choice(['list', 'restore']), default='list')
def cli(site_name, live, op):
    click.clear()
    click.secho('Restore: {}'.format(site_name), fg=WHITE, bold=True)
    click.echo()
    pillar_folder = get_pillar_folder()
    click.secho('pillar: {}'.format(pillar_folder), fg=CYAN)

    if live:
        click.secho('is ALIVE!', fg=YELLOW, bold=True)
        server_name = get_server_name_live(pillar_folder, site_name)
    else:
        click.secho('testing, testing...', fg=CYAN, bold=True)
        server_name = get_server_name_test(pillar_folder, site_name)
    click.secho('server_name: {}'.format(server_name), fg=CYAN)
    site_info = SiteInfo(server_name, site_name)
    repo = '{}{}/backup'.format(site_info.rsync_ssh, site_name)
    click.secho(repo, fg=CYAN)

    if op == 'list':
        result = subprocess.call([
            'duplicity',
            'collection-status',
            repo
        ])
        if result:
            raise Exception("Cannot get collection status [{}].".format(result))

    click.echo()


if __name__ == '__main__':
    cli()
