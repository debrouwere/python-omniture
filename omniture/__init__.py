# encoding: utf-8

from account import Account, Suite
from elements import Value, Element, Segment
from query import Query
from reports import InvalidReportError, Report, OverTimeReport, \
    RankedReport, TrendedReport, DataWarehouseReport


def authenticate(username, secret=None, endpoint=Account.DEFAULT_ENDPOINT, prefix='', suffix=''):
    # if no secret is specified, we will assume that instead 
    # we have received a dictionary with credentials (such as
    # from os.environ)
    if not secret:
        source = username
        key_to_username = utils.affix(prefix, 'OMNITURE_USERNAME', suffix)
        key_to_secret = utils.affix(prefix, 'OMNITURE_SECRET', suffix)
        username = source[key_to_username]
        secret = source[key_to_secret]

    return Account(username, secret, endpoint)


def queue(queries):
    if isinstance(queries, dict):
        queries = queries.values()

    for query in queries:
        query.queue()


def sync(queries, heartbeat=None, interval=1):
    """
    `omniture.sync` will queue a number of reports and then 
    block until the results are ready.

    Queueing reports is idempotent, meaning that you can also 
    use `omniture.sync` to fetch the results for queries that 
    have already been queued: 

        query = mysuite.report.range('2013-06-06').over_time('pageviews', 'page')
        omniture.queue(query)
        omniture.sync(query)
    """

    queue(queries)

    if isinstance(queries, list):
        return [query.sync(heartbeat, interval) for query in queries]
    elif isinstance(queries, dict):
        return {key: query.sync(heartbeat, interval) for key, query in queries.items()}
    else:
        message = "Queries should be a list or a dictionary, received: {}".format(
            queries.__class__)
        raise ValueError(message)
