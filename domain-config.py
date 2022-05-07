# -*- encoding: utf-8 -*-
import attr
import fnmatch
import json
import pathlib
import requests
import yaml

from http import HTTPStatus
from os import environ
from rich import print as rprint
from rich.console import Console
from rich.pretty import pprint


console = Console()


@attr.s
class Droplet:
    droplet_id = attr.ib()
    minion_id = attr.ib()
    memory = attr.ib()
    disk = attr.ib()
    price_monthly = attr.ib()
    tags = attr.ib()
    domains = attr.ib()


def display_domains(domains):
    count = 0
    for domain_name, config in domains.items():
        count = count + 1
        ssl = False
        print()
        if "ssl" in config:
            ssl = True
        console.print(
            "{}. {}{}".format(
                count, "https://" if ssl else "http://", domain_name
            )
        )
        console.print("- {}".format(config["minion"]))
        if "testing" in config:
            console.print("- Test Site")
        if "profile" in config:
            profile = config["profile"]
            if profile == "php":
                profile = "{} (PHP)".format(config["php_profile"].capitalize())
            else:
                profile = "{}".format(profile.capitalize())
            console.print("- {}".format(profile))
        if "backup" in config:
            console.print("- backup")
        is_promtail = is_raygun = False
        if "env" in config:
            env = config["env"]
            if "norecaptcha_site_key" in env:
                console.print("- captcha (Google)")
            if "raygun4py_api_key" in env:
                is_raygun = True
            if "sparkpost_api_key" in env:
                console.print("- email (SparkPost)")
        if "promtail" in config:
            is_promtail = True
        if is_promtail or is_raygun:
            x = "{}".format("Promtail" if is_promtail else "RayGun")
            console.print("- monitor ({})".format(x))
        if ssl:
            certificate = ""
            if "letsencrypt" in config:
                certificate = "LetsEncrypt"
            console.print(
                "- ssl{}".format(
                    " ({})".format(certificate) if certificate else ""
                )
            )


def get_digital_ocean():
    """

    How To Use Web APIs in Python 3
    https://www.digitalocean.com/community/tutorials/how-to-use-web-apis-in-python-#!/usr/bin/env python3

    """
    result = []
    api_token = environ["DIGITAL_OCEAN_TOKEN"]
    api_url_base = "https://api.digitalocean.com/v2/"
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer {0}".format(api_token),
    }
    api_url = "{}droplets".format(api_url_base)
    response = requests.get(api_url, headers=headers)
    if response.status_code == HTTPStatus.OK:
        data = json.loads(response.content.decode("utf-8"))
        droplets = data["droplets"]
        for droplet in droplets:
            minion_id = droplet["name"]
            size = droplet["size"]
            # 06/05/2022, The project does not appear in the Droplet data, so
            # use the tags for now...
            tags = droplet["tags"]
            result.append(
                Droplet(
                    droplet_id=droplet["id"],
                    minion_id=minion_id,
                    memory=droplet["memory"],
                    disk=droplet["disk"],
                    price_monthly=size["price_monthly"],
                    tags=[x for x in tags],
                    domains=[],
                )
            )
    else:
        pprint(response, expand_all=True)
        raise Exception(
            "Error from the Digital Ocean API: {}".format(response.status_code)
        )
    return result
    # return dict(sorted(result.items()))


class Linode:
    def __init__(self):
        self.api_token = environ["LINODE_TOKEN"]
        self.api_url_base = "https://api.linode.com/v4/linode/"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {0}".format(self.api_token),
        }
        self.linode_types = {}

    def get_linodes(self):
        """

        From, Create a Linode Using the Linode API
        https://www.linode.com/docs/guides/getting-started-with-the-linode-api/

        """
        result = []
        api_url = "{}instances".format(self.api_url_base)
        response = requests.get(api_url, headers=self.headers)
        if response.status_code == HTTPStatus.OK:
            data = json.loads(response.content.decode("utf-8"))
            # pprint(data, expand_all=True)
            droplets = data["data"]
            for droplet in droplets:
                minion_id = droplet["label"]
                linode_type = self.get_linode_type(droplet["type"])
                # size = droplet["size"]
                # tags = droplet["tags"]
                specs = droplet["specs"]
                result.append(
                    Droplet(
                        droplet_id=droplet["id"],
                        minion_id=minion_id,
                        memory=specs["memory"],
                        disk=specs["disk"],
                        price_monthly=linode_type["price"]["monthly"],
                        tags=[],
                        domains=[],
                    )
                )
        else:
            pprint(response, expand_all=True)
            raise Exception(
                "Error from the Linode API: {}".format(response.status_code)
            )
        return result

    def get_linode_type(self, linode_type):
        """

        https://www.linode.com/docs/api/linode-types/#type-view

        """
        if linode_type in self.linode_types:
            pass
        else:
            api_url = "{}types/{}".format(self.api_url_base, linode_type)
            response = requests.get(api_url, headers=self.headers)
            if response.status_code == HTTPStatus.OK:
                data = json.loads(response.content.decode("utf-8"))
                self.linode_types["linode_type"] = data
            else:
                pprint(response, expand_all=True)
                raise Exception(
                    "Error from the Linode types API: {}".format(
                        response.status_code
                    )
                )
        return self.linode_types["linode_type"]


def get_domains():
    """Get the config for each site (domain name) from the Salt pillar."""
    result = {}
    pillar_folder = pathlib.Path.home().joinpath("Private", "deploy")
    for folder in pillar_folder.iterdir():
        if folder.is_dir() and folder.name.startswith("pillar-"):
            wildcard = get_wildcard(folder)
            result.update(get_domain_names(folder, wildcard))
    return result


def get_wildcard(pillar_folder):
    """Get the config for the wildcard include files.

    The ``top.sls`` file for our pillar, includes wildcards e.g::

      '*':
        - global.users
      'kb-* and not kb-vpn':
        - config.django
        - config.monitor
        - config.nginx

    This method retrieves the *wildcard* config, so it can be merged into the
    site later on (using ``match_minion``).

    """
    result = {}
    with open(pathlib.Path(pillar_folder, "top.sls")) as f:
        # load the 'top.sls' file
        data = yaml.safe_load(f)
        base = data["base"]
        for host_name, config in base.items():
            if "*" in host_name:
                result[host_name] = {}
                for include in config:
                    if isinstance(include, str):
                        # not sure if / why we need to do this...
                        if include.startswith("sites"):
                            pass
                        else:
                            # convert include to file and path
                            # e.g. 'config.monitor' to 'config/monitor.sls'
                            path_file = include.split(".")
                            path_file[-1] = path_file[-1] + ".sls"
                            with open(
                                pathlib.Path(pillar_folder, *path_file)
                            ) as f:
                                include_config = yaml.safe_load(f)
                                result[host_name].update(include_config)
    return result


def get_domain_names(pillar_folder, wildcard):
    """Find the server configuration for each site / domain name.

    .. warning:: We add the configuration for the site / domain name after
                 merging the configuration for the server
                 (including *wildcard* data).
                 Salt probably resolves this in a different order!

    """
    result = {}
    with open(pathlib.Path(pillar_folder, "top.sls")) as f:
        # load the 'top.sls' file
        data = yaml.safe_load(f)
        base = data["base"]
        for host_name, base_config in base.items():
            if "*" in host_name:
                # exclude wildcard e.g. 'pc-*' (see 'get_wildcard')
                pass
            else:
                server_config = {}
                for include in base_config:
                    if isinstance(include, str):
                        # convert include to file and path
                        # e.g. 'sites.cw-3' to 'sites/cw-3.sls'
                        path_file = include.split(".")
                        path_file[-1] = path_file[-1] + ".sls"
                        with open(pathlib.Path(pillar_folder, *path_file)) as f:
                            server_config.update(yaml.safe_load(f))
                if "sites" in server_config:
                    sites = server_config.pop("sites")
                    for domain_name, domain_config in sites.items():
                        # config for domain name (site)
                        result[domain_name] = {}
                        # merge in the *wildcard* config
                        result[domain_name].update(
                            merge_wildcard(host_name, wildcard)
                        )
                        # merge in the config for this server
                        result[domain_name].update(server_config)
                        # add the server (host) name
                        result[domain_name].update({"minion": host_name})
                        # finally - merge the domain config
                        result[domain_name].update(domain_config)
    return result


def json_dump_domains(domains):
    # file_name = "temp.json"
    # with open(file_name, "w") as f:
    #     json.dump(domains, f, indent=4)
    # write only required data to ``domains.json``
    # if you want to see all the data, then uncomment just above...
    data = {}
    for domain_name, config in domains.items():
        data.update({domain_name: {"minion_id": config["minion"]}})
    file_name = "domains.json"
    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
    rprint("[yellow]1. 'json_dump_domains' to '{}'...".format(file_name))


def json_dump_droplets(droplets):
    data = []
    file_name = "droplets.json"
    for droplet in droplets:
        data.append(attr.asdict(droplet))
    with open(file_name, "w") as f:
        json.dump(data, f, indent=4)
    rprint("[yellow]2. 'json_dump_droplets' to '{}'...".format(file_name))


def match_minion(minion_id, salt_top):
    """Copied from ``_match`` (see ``lib/pillarinfo.py`` in ``fabric``."""
    result = False
    if minion_id is None:
        result = True
    else:
        # 20/04/2021, Try and handle ``and not``
        # (when I don't really understand parsing)
        # e.g. 'drop-* and not drop-vpn'
        tokens = salt_top.split(" ")
        index_and = index_not = minion_not = None
        try:
            index_and = tokens.index("and")
            index_not = tokens.index("not")
        except ValueError:
            pass
        # if minion_id == "kb-a" and index_and and index_not:
        # import pdb; pdb.set_trace()
        if (
            index_and
            and index_not
            and index_and > 0
            and (index_and + 1 == index_not)
            and (index_not + 2 == len(tokens))
        ):
            minion_not = tokens[index_not + 1].strip()
            pos = salt_top.find(" and ")
            salt_top = salt_top[:pos].strip()
        # exclude the ``and not`` value e.g. ``drop-vpn``
        if minion_not and minion_not == minion_id:
            pass
        else:
            result = fnmatch.fnmatch(minion_id, salt_top)
            if not result:
                for item in salt_top.split(","):
                    result = fnmatch.fnmatch(minion_id, item)
                    if result:
                        break
    return result


def merge_wildcard(host_name, wildcard):
    """Merge configuration from files matching the wildcard.

    e.g. ``nc-*`` matches ``nc-a``, so ``nc-a`` will include the
    configuration data from ``nc-*``.

    """
    result = {}
    for wildcard_host, config in wildcard.items():
        if match_minion(host_name, wildcard_host):
            result.update(config)
    return result


def main():
    # find all the domains in the salt pillar
    domains = dict(sorted(get_domains().items()))
    json_dump_domains(domains)
    # display_domains(domains)

    # find the domain names for each minion (server)
    minions = {}
    for domain_name, config in domains.items():
        minion_id = config["minion"]
        if not minion_id in minions:
            minions[minion_id] = []
        minions[minion_id].append(domain_name)
    # pprint(minions, expand_all=True)

    # get a list of cloud servers (droplets)
    droplets = []
    droplets = droplets + get_digital_ocean()
    droplets = droplets + Linode().get_linodes()

    # link the domain names to the droplets
    for droplet in droplets:
        minion_id = droplet.minion_id
        if minion_id in minions:
            droplet.domains = minions.pop(minion_id)
    json_dump_droplets(droplets)

    # use the tag to link droplets to a contact
    # contacts = {}
    # for droplet in droplets:
    #     for tag in droplet.tags:
    #         if not tag in contacts:
    #             contacts[tag] = []
    #         contacts[tag].append(droplet)
    # pprint(contacts, expand_all=True)

    # display any minions which are not allocated to a droplet
    print()
    rprint("[cyan]List of Salt minions NOT allocated to a Cloud Server...")
    rprint(
        "[cyan]Note: this is most likely because "
        "the customer is paying for the hosting!"
    )
    pprint(minions, expand_all=True)


if __name__ == "__main__":
    main()
