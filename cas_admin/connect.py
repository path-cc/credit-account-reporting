import click
from elasticsearch import Elasticsearch


def connect(
    es_host="localhost",
    es_user=None,
    es_pass=None,
    es_use_https=False,
    es_ca_certs=None,
    **kwargs,
):
    """Returns an Elasticsearch client"""

    # Split off port from host if included
    if ":" in es_host and len(es_host.split(":")) == 2:
        [es_host, es_port] = es_host.split(":")
        es_port = int(es_port)
    elif ":" in es_host:
        click.echo(f"Ambiguous hostname:port in given host: {es_host}", err=True)
        sys.exit(1)
    else:
        es_port = 9200
    es_client = {"host": es_host, "port": es_port}

    # Include username and password if both are provided
    if es_user is None and es_pass is None:
        pass
    elif (es_user is None) != (es_pass is None):
        click.echo("Only one of es_user and es_pass have been defined", err=True)
        click.echo("Connecting to Elasticsearch anonymously", err=True)
    else:
        es_client["http_auth"] = (es_user, es_pass)

    # Only use HTTPS if CA certs are given or if certifi is available
    if es_use_https:
        if es_ca_certs is not None:
            es_client["ca_certs"] = es_ca_certs
        elif importlib.util.find_spec("certifi") is not None:
            pass
        else:
            click.echo(
                "Using HTTPS with Elasticsearch requires that either es_ca_certs be provided or certifi library be installed",
                err=True,
            )
            sys.exit(1)
        es_client["use_ssl"] = True
        es_client["verify_certs"] = True

    return Elasticsearch([es_client])
