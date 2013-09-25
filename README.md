# python-omniture

`python-omniture` is a wrapper around the Adobe Omniture web analytics API.

It is not meant to be comprehensive. Instead, it provides a high-level interface
to certain common kinds of queries, and allows you to do construct other queries
closer to the metal.

## Installation

Through PyPI:

    pip install omniture

Latest and greatest: 

    pip install git+git://github.com/stdbrouw/python-omniture.git

## Authentication

The most straightforward way to authenticate is with: 

    import omniture
    account = omniture.authenticate('my_username', 'my_secret')

However, to avoid hardcoding passwords, instead you can also put your username
and password in unix environment variables (e.g. in your `.bashrc`):

    export OMNITURE_USERNAME=my_username
    export OMNITURE_SECRET=my_secret

With your credentials in the environment, you can then log in as follows:

    import os
    import omniture
    account = omniture.authenticate(os.environ)

## Account and suites

You can very easily access some basic information about your account and your
reporting suites:

    print analytics.suites
    suite = analytics.suites['guardiangu-network']
    print suite
    print len(suite.evars)
    print suite.segments
    print suite.elements

You can refer to suites, segments, elements and so on using both their
human-readable name or their id. So for example `suite.segments['pageviews']` and `suite.segments['Page Views']` will work exactly the same. This is especially useful in cases when segment or metric identifiers are long strings of gibberish. That way you don't have to riddle your code with references to `evar16` or `custom4` and instead can call them by their title.

## Running a report

`python-omniture` can run ranked, trended and "over time" reports

* over_time
  * supports multiple metrics but only one element: time
  * useful if you need information on a per-page basis
  * supports hourly reporting (and up)
* ranked
  * ranks pages in relation to the metric
  * one number (per metric) for the entire reporting period
  * only supports daily, weekly and monthly reporting
* trended
  * movement of a single element and metric over time (e.g. visits to world news over time)
  * supports hourly reporting (and up)

    report = network.report \
        .over_time(metrics=['pageviews', 'visitors']) \
        .range('2013-05-01', '2013-05-31', granularity='month') \
        .sync()

Accessing the data in a report works as follows:

    report.data['pageviews']

### Getting down to the plumbing.

This module is still in beta and you should expect some things not to work. In particular, trended reports have not seen much love (though they should work), and data warehouse reports don't work at all.

In these cases, it can be useful to use the lower-level access this module provides through `mysuite.report.set` -- you can pass set either a key and value, a dictionary with key-value pairs or you can pass keyword arguments. These will then be added to the raw query. You can always check what the raw query is going to be with the `build` method on queries.

    query = network.report \
        .over_time(metrics=['pageviews', 'visitors']) \
        .set(dateGranularity='month')
        .set({'segmentId': 'social'})
        .set('name', 'my report name')

    print query.build()

### Running multiple reports

If you're interested in automating a large number of reports, you can speed up the 
execution by first queueing all the reports and only _then_ waiting on the results.

Here's an example:

    queue = []
    for segment in segments:
        report = network.report \
            .range('2013-05-01', '2013-05-31', granularity='day') \
            .over_time(metrics=['pageviews']) \
            .filter(segment=segment)
        queue.append(report)

    heartbeat = lambda: sys.stdout.write('.')
    reports = omniture.sync(queue, heartbeat)

    for report in reports:
        print report.segment
        print report.data['pageviews']

`omniture.sync` can queue up (and synchronize) both a list of reports, or a dictionary.
