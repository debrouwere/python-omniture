import omniture
import sys
import os
from pprint import pprint

analytics = omniture.Account()
analytics.authenticate(os.environ)

#print analytics.suites
print analytics.suites['guardiangu-parioli-taste-of-rome']
print analytics.suites['Media Prof Network']
network = analytics.suites['guardiangu-network']
print len(network.evars)
#pprint(network.segments)
print network.segments['First Time Visitors']

segments = [
    'UK (Locked)', 
    'US (Locked)',
    ]

queue = []

for segment in segments:
    report = network.report \
        .range('2013-05-01', '2013-05-31', granularity='day') \
        .over_time(metrics=['pageviews']) \
        .filter(segment=segment)

    queue.append(report)

def heartbeat():
    sys.stdout.write('.')
    sys.stdout.flush()

reports = omniture.sync(queue, heartbeat)

for report in reports:
    print report.segment
    print report.data['pageviews']

