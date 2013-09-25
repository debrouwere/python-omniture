# encoding: utf-8

from elements import Value, Element, Segment
import utils


class InvalidReportError(Exception):
    def normalize(self, error):
        print 'error', error

        if 'error_msg' in error:
            return {
                'status': error['status'],
                'code': error['error_code'],
                'message': error.get('error_msg', ''),
            }
        else:
            return {
                'status': error['statusMsg'],
                'code': error['status'],
                'message': error.get('statusDesc', ''),
            }

    def __init__(self, error):
        error = self.normalize(error)
        message = "{status}: {message} ({code})".format(**error)
        super(InvalidReportError, self).__init__(message)


#  TODO: also make this iterable (go through rows)
class Report(object):
    def process(self):
        self.status = self.raw['status']
        self.timing = {
            'queue': float(self.raw['waitSeconds']),
            'execution': float(self.raw['runSeconds']),
        }
        self.report = report = self.raw['report']
        self.metrics = Value.list('metrics', report['metrics'], self.suite, 'name', 'id')
        self.elements = Value.list('elements', report['elements'], self.suite, 'name', 'id')
        self.period = report['period']
        segment = report['segment_id']
        if len(segment):
            self.segment = self.query.suite.segments[report['segment_id']]
        else:
            self.segment = None

        self.data = utils.AddressableDict(self.metrics)
        for column in self.data:
            column.value = []

    def to_dataframe(self):
        import pandas as pd
        raise NotImplementedError()
        # return pd.DataFrame()

    def serialize(self, verbose=False):
        if verbose:
            facet = 'title'
        else:
            facet = 'id'

        d = {}
        for el in self.data:
            key = getattr(el, facet)
            d[key] = el.value
        return d

    def __init__(self, raw, query):
        #from pprint import pprint
        #pprint(raw)

        self.raw = raw
        self.query = query
        self.suite = query.suite
        self.process()

    def __repr__(self):
        info = {
            'metrics': ", ".join(map(str, self.metrics)), 
            'elements': ", ".join(map(str, self.elements)), 
        }
        return "<omniture.RankedReport (metrics) {metrics} (elements) {elements}>".format(**info)

class OverTimeReport(Report):
    def process(self):
        super(OverTimeReport, self).process()

        # TODO: this works for over_time reports and I believe for ranked
        # reports as well, but trended reports have their data in 
        # `data.breakdown:[breakdown:[counts]]`
        for row in self.report['data']:
            for i, value in enumerate(row['counts']):
                if self.metrics[i].type == 'number':
                    value = float(value)
                self.data[i].append(value)

OverTimeReport.method = 'QueueOvertime'


class RankedReport(Report):
    def process(self):
        super(RankedReport, self).process()

        for row in self.report['data']:
            for i, value in enumerate(row['counts']):
                if self.metrics[i].type == 'number':
                    value = float(value)
                self.data[i].append((row['name'], row['url'], value))

RankedReport.method = 'QueueRanked'


class TrendedReport(Report):
    def process(self):
        super(TrendedReport, self).process()

TrendedReport.method = 'QueueTrended'


class DataWarehouseReport(object):
    pass

DataWarehouseReport.method = 'Request'

