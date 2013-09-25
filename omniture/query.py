# encoding: utf-8

import time
from copy import copy
import functools
from elements import Value, Element, Segment
import reports
import utils


def immutable(method):
    @functools.wraps(method)
    def wrapped_method(self, *vargs, **kwargs):
        obj = self.clone()
        method(obj, *vargs, **kwargs)
        return obj

    return wrapped_method


class Query(object):
    GRANULARITY_LEVELS = ['hour', 'day', 'month']

    def __init__(self, suite):
        self.suite = suite
        self.raw = {}
        self.id = None
        self.report = None

    def _normalize_value(self, value, category):
        if isinstance(value, Value):
            return value
        else:
            return getattr(self.suite, category)[value]

    def _serialize_value(self, value, category):
        return self._normalize_value(value, category).serialize()

    def _serialize_values(self, values, category):
        if not isinstance(values, list):
            values = [values]

        return [self._serialize_value(value, category) for value in values]

    def _serialize(self, obj):
        if isinstance(obj, list):
            return [self._serialize(el) for el in obj]
        elif isinstance(obj, Value):
            return obj.serialize()
        else:
            return obj

    def clone(self):
        query = Query(self.suite)
        query.raw = copy(self.raw)
        query.report = self.report
        return query

    @immutable
    def range(self, start, stop=None, months=0, days=0, granularity=None):
        start = utils.date(start)
        stop = utils.date(stop)

        if days or months:
            stop = start + relativedelta(days=days-1, months=months)
        else:
            stop = stop or start

        if start == stop:
            self.raw['date'] = start.isoformat()
        else:
            self.raw.update({
                'dateFrom': start.isoformat(),
                'dateTo': stop.isoformat(),
            })

        if granularity:
            if granularity not in self.GRANULARITY_LEVELS:
                levels = ", ".join(self.GRANULARITY_LEVELS)
                raise ValueError("Granularity should be one of: " + levels)

            self.raw['dateGranularity'] = granularity

        return self

    @immutable
    def set(self, key=None, value=None, **kwargs):
        """
        `set` is a way to add raw properties to the request, 
        for features that python-omniture does not support but the 
        SiteCatalyst API does support. For convenience's sake, 
        it will serialize Value and Element objects but will 
        leave any other kind of value alone.
        """

        if key and value:
            self.raw[key] = self._serialize(value)
        elif key or kwargs:
            properties = key or kwargs
            for key, value in properties.items():
                self.raw[key] = self._serialize(value)
        else:
            raise ValueError("Query#set requires a key and value, a properties dictionary or keyword arguments.")

        return self

    @immutable
    def sort(self, facet):
        #self.raw['sortBy'] = facet
        raise NotImplementedError()
        return self

    @immutable
    def filter(self, segments=None, segment=None):
        # It would appear to me that 'segment_id' has a strict subset
        # of the functionality of 'segments', but until I find out for
        # sure, I'll provide both options.
        if segments:
            self.raw['segments'] = self._serialize_values(segments, 'segments')
        elif segment:
            self.raw['segment_id'] = self._normalize_value(segment, 'segments').id
        else:
            raise ValueError()

        return self

    @immutable
    def ranked(self, metrics, elements):
        self._serialize_values(metrics, 'metrics')

        self.report = reports.RankedReport
        self.raw['metrics'] = self._serialize_values(metrics, 'metrics')
        self.raw['elements'] = self._serialize_values(elements, 'elements')
        return self

    @immutable
    def trended(self, metric, element):
        if isinstance(metric, list) or isinstance(element, list):
            raise ValueError("Trended reports can only be generated for one metric and one element.")

        self.report = reports.TrendedReport
        self.raw['metrics'] = self._serialize_values(metric, 'metrics')
        self.raw['elements'] = self._serialize_values(element, 'elements')
        return self

    @immutable
    def over_time(self, metrics):
        self.report = reports.OverTimeReport
        self.raw['metrics'] = self._serialize_values(metrics, 'metrics')
        return self

    # TODO: data warehouse reports are a work in progress
    @immutable
    def data(self, metrics, breakdowns):
        self.report = reports.DataWarehouseReport
        self.raw['metrics'] = self._serialize_values(metrics, 'metrics')
        # TODO: haven't figured out how breakdowns work yet
        self.raw['breakdowns'] = False
        return self

    def build(self):
        if self.report == reports.DataWarehouseReport:
            return utils.translate(self.raw, {
                'metrics': 'Metric_List',
                'breakdowns': 'Breakdown_List',
                'dateFrom': 'Date_From',
                'dateTo': 'Date_To',
                # is this the correct mapping?
                'date': 'Date_Preset',
                'dateGranularity': 'Date_Granularity',
                })
        else:
            return {'reportDescription': self.raw}

    def queue(self):
        q = self.build()
        self.id = self.suite.request('Report', self.report.method, q)['reportID']
        return self

    def probe(self, fn, heartbeat=None, interval=1, soak=False):
        status = 'not ready'
        while status == 'not ready':
            if heartbeat:
                heartbeat()
            time.sleep(interval)
            response = fn()
            status = response['status']
            
            if not soak and status not in ['not ready', 'done', 'ready']:
                raise reports.InvalidReportError(response)

        return response

    # only for SiteCatalyst queries
    def sync(self, heartbeat=None, interval=1):
        if not self.id:
            self.queue()

        # this looks clunky, but Omniture sometimes reports a report
        # as ready when it's really not
        check_status = lambda: self.suite.request('Report', 'GetStatus', {'reportID': self.id})
        get_report = lambda: self.suite.request('Report', 'GetReport', {'reportID': self.id})
        status = self.probe(check_status, heartbeat, interval, soak=True)
        response = self.probe(get_report, heartbeat, interval)
        return self.report(response, self)

    # only for SiteCatalyst queries
    def async(self, callback=None, heartbeat=None, interval=1):
        if not self.id:
            self.queue()

        raise NotImplementedError()

    # only for Data Warehouse queries
    def request(self, name='python-omniture query', ftp=None, email=None):
        raise NotImplementedError()

    def cancel(self):
        if self.report == reports.DataWarehouseReport:
            return self.suite.request('DataWarehouse', 'CancelRequest', {'Request_Id': self.id})
        else:
            return self.suite.request('Report', 'CancelReport', {'reportID': self.id})
