# -*- encoding: utf-8 -*-
import fnmatch
import pathlib
import yaml

from rich.console import Console
from rich.pretty import pprint


console = Console()


def get_domains():
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
    domains = dict(sorted(get_domains().items()))
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


if __name__ == "__main__":
    main()
