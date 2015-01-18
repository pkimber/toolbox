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


def _heading(site_name, op):
    h = None
    click.clear()
    if op == 'list':
        h = 'List'
    else:
        raise NotImplementedError("Unknown 'op': [{}]".format(op))
    click.secho('{}: {}'.format(h, site_name), fg=WHITE, bold=True)


def _list(repo):
        result = subprocess.call([
            'duplicity',
            'collection-status',
            repo
        ])
        if result:
            raise Exception("Cannot get collection status [{}].".format(result))


def _repo(site_info, site_name, what):
    result = '{}{}/{}'.format(site_info.rsync_ssh, site_name, what)
    click.secho(result, fg=CYAN)
    return result


def _server_name(site_name, live, pillar_folder):
    result = None
    if live:
        click.secho('is ALIVE!', fg=YELLOW, bold=True)
        result = get_server_name_live(pillar_folder, site_name)
    else:
        click.secho('testing, testing...', fg=CYAN, bold=True)
        result = get_server_name_test(pillar_folder, site_name)
    click.secho('server_name: {}'.format(result), fg=CYAN)
    return result


@click.command()
@click.option('-s', '--site-name', prompt=True)
@click.option('--live/--test', default=False)
@click.option('--op', type=click.Choice(['list', 'restore']), default='list')
@click.option('--what', type=click.Choice(['backup', 'files']), prompt=True)
def cli(site_name, live, op, what):
    _heading(site_name, op)
    pillar_folder = get_pillar_folder()
    server_name = _server_name(site_name, live, pillar_folder)
    site_info = SiteInfo(server_name, site_name)
    repo = _repo(site_info, site_name, what)
    if op == 'list':
        _list(repo)
    click.echo()


if __name__ == '__main__':
    cli()
