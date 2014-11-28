import click

CYAN = 'cyan'
YELLOW = 'yellow'
WHITE = 'white'

URL = 'http://localhost:8000/api/0.1/'
USERNAME = 'staff'
PASSWORD = 'letmein'

all_colors = 'black', 'red', 'green', 'yellow', 'blue', 'magenta', \
             'cyan', 'white'

STATUS_CODES = {
    200: 'OK',
    201: 'CREATED',
    204: 'NO CONTENT',
    400: 'BAD REQUEST',
}


def echo_req(title, verb, url, data=None):
    if data:
        click.secho(json.dumps(data, indent=2), fg=YELLOW)
    click.echo()


def echo_res(r):
    click.secho(
        'STATUS: {} {}'.format(r.status_code, STATUS_CODES[r.status_code]),
        fg=CYAN,
        bold=True,
    )
    if not r.status_code == 204:
        click.secho(json.dumps(r.json(), indent=2), fg=CYAN)
    click.echo()


def login():
    url = '{}token/'.format(URL)
    data = {'username': USERNAME, 'password': PASSWORD}
    echo_req('login', 'POST', url, data)
    r = requests.post(url, data=data)
    echo_res(r)
    assert(r.status_code == 200)
    global token
    token = r.json().get('token')


def users_current():
    url = '{}users/current/'.format(URL)
    headers = {'Content-type': 'application/json', 'Authorization': 'Token {}'.format(token)}
    echo_req('current user', 'GET', url)
    r = requests.get(url, headers=headers)
    echo_res(r)
    assert(r.status_code == 200)
    user_id = r.json().get('id')


def put_users_current_params():
    url = '{}users/current/params/'.format(URL)
    data = {'name': 'Patrick', 'town': 'Okehampton'}
    headers = {'Content-type': 'application/json', 'Authorization': 'Token {}'.format(token)}
    echo_req('current user - params', 'PUT', url, data)
    r = requests.put(url, data=json.dumps(data), headers=headers)
    echo_res(r)
    assert(r.status_code == 204)


def get_users_current_params():
    url = '{}users/current/params/'.format(URL)
    headers = {'Content-type': 'application/json', 'Authorization': 'Token {}'.format(token)}
    echo_req('current user - params', 'GET', url)
    r = requests.get(url, headers=headers)
    echo_res(r)
    assert(r.status_code == 200)


def get_datatypes():
    url = '{}datatypes/'.format(URL)
    headers = {'Content-type': 'application/json', 'Authorization': 'Token {}'.format(token)}
    echo_req('data types', 'GET', url)
    r = requests.get(url, headers=headers)
    echo_res(r)
    assert(r.status_code == 200)
    data_type_count = len(r.json())
    data_type_id = None
    if data_type_count:
        data_type_id = r.json()[0].get('id')


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
