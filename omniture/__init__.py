import requests
import binascii
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta
from copy import copy, deepcopy
import sha
import json
import functools
import utils


class Value(object):
    def __init__(self, title, id, parent, extra={}):
        self.title = title
        self.id = id
        self.parent = parent
        self.properties = {'id': id}

        for k, v in extra.items():
            setattr(self, k, v)

    @classmethod
    def list(cls, name, items, parent, title='title', id='id'):
        values = [cls(item[title], item[id], parent, item) for item in items]
        return utils.AddressableList(values, name)

    def __repr__(self):
        return "<{title}: {id} in {parent}>".format(**self.__dict__)

    def copy(self):
        value = self.__class__(self.title, self.id, self.parent)
        value.properties = copy(self.properties)
        return value

    def serialize(self):
        return self.properties

    def __str__(self):
        return self.title


class Element(Value):
    def range(self, *vargs):
        l = len(vargs)
        if l == 1:
            start = 0
            stop = vargs[0]
        elif l == 2:
            start, stop = vargs

        top = stop - start

        element = self.copy()
        element.properties['startingWith'] = str(start)
        element.properties['top'] = str(top)

        return element

    def search(self, keywords, type='AND'):
        type = type.upper()

        types = ['AND', 'OR', 'NOT']
        if type not in types:
            raise ValueError("Search type should be one of: " + ", ".join(types))

        element = self.copy()
        element.properties['search'] = {
            'type': type, 
            'keywords': utils.wrap(keywords), 
        }
        return element

    def select(self, keys):
        element = self.copy()
        element.properties['selected'] = utils.wrap(keys)
        return element


class Segment(Element):
    pass


class Account(object):
    def __init__(self, endpoint='https://api.omniture.com/admin/1.3/rest/'):
        self.endpoint = endpoint

    def initialize(self):
        data = self.request('Company', 'GetReportSuites')['report_suites']
        suites = [Suite(suite['site_title'], suite['rsid'], self) for suite in data]
        self.suites = utils.AddressableList(suites)

    def request(self, api, method, query={}):
        response = requests.post(
            self.endpoint, 
            params={'method': api + '.' + method}, 
            data=json.dumps(query), 
            headers=self._build_token()
            )
        return response.json()

    def _serialize_header(self, properties):
        header = []
        for key, value in properties.items():
            header.append('{key}="{value}"'.format(key=key, value=value))
        return ', '.join(header)

    def _build_token(self):
        nonce = str(time.time())
        base64nonce = binascii.b2a_base64(binascii.a2b_qp(nonce))
        created_date = datetime.today().isoformat() + 'Z'
        sha_object = sha.new(nonce + created_date + self.secret)
        password_64 = binascii.b2a_base64(sha_object.digest())

        properties = {
            "Username": self.username, 
            "PasswordDigest": password_64.strip(),
            "Nonce": base64nonce.strip(),
            "Created": created_date,
        }
        header = 'UsernameToken ' + self._serialize_header(properties)

        return {'X-WSSE': header}

    def authenticate(self, username, secret=None, prefix='', suffix=''):
        if secret:
            self.username = username
            self.secret = secret
        else:
            source = username
            username = utils.affix(prefix, 'OMNITURE_USERNAME', suffix)
            secret = utils.affix(prefix, 'OMNITURE_SECRET', suffix)
            self.username = source[username]
            self.secret = source[secret]

        self.initialize()


class Suite(Value):
    def request(self, api, method, query={}):
        raw_query = {}
        raw_query.update(query)
        if 'reportDescription' in raw_query:
            raw_query['reportDescription']['reportSuiteID'] = self.id
        elif api == 'ReportSuite':
            raw_query['rsid_list'] = [self.id]

        return self.account.request(api, method, raw_query)

    def __init__(self, title, id, account):
        super(Suite, self).__init__(title, id, account)

        self.account = account

    @property
    @utils.memoize
    def metrics(self):
        data = self.request('ReportSuite', 'GetAvailableMetrics')[0]['available_metrics']
        return Value.list('metrics', data, self, 'display_name', 'metric_name')

    @property
    @utils.memoize
    def elements(self):
        data = self.request('ReportSuite', 'GetAvailableElements')[0]['available_elements']
        return Element.list('elements', data, self, 'display_name', 'element_name')

    @property
    @utils.memoize
    def evars(self):
        data = self.request('ReportSuite', 'GetEVars')[0]['evars']
        return Value.list('evars', data, self, 'name', 'evar_num')

    @property
    @utils.memoize
    def segments(self):
        data = self.request('ReportSuite', 'GetSegments')[0]['sc_segments']
        return Segment.list('segments', data, self, 'name', 'id')

    @property
    def report(self):
        return Query(self)


def immutable(method):
    @functools.wraps(method)
    def wrapped_method(self, *vargs, **kwargs):
        obj = self.clone()
        method(obj, *vargs, **kwargs)
        return obj

    return wrapped_method


class Query(object):
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

        self.report = RankedReport
        self.raw['metrics'] = self._serialize_values(metrics, 'metrics')
        self.raw['elements'] = self._serialize_values(elements, 'elements')
        return self

    @immutable
    def trended(self, metric, element):
        if isinstance(metric, list) or isinstance(element, list):
            raise ValueError("Trended reports can only be generated for one metric and one element.")

        self.report = TrendedReport
        self.raw['metrics'] = self._serialize_values(metric, 'metrics')
        self.raw['elements'] = self._serialize_values(element, 'elements')
        return self

    @immutable
    def over_time(self, metrics):
        self.report = OverTimeReport
        self.raw['metrics'] = self._serialize_values(metrics, 'metrics')
        return self

    # TODO: data warehouse reports are a work in progress
    @immutable
    def data(self, metrics, breakdowns):
        self.report = DataWarehouseReport
        self.raw['metrics'] = self._serialize_values(metrics, 'metrics')
        # TODO: haven't figured out how breakdowns work yet
        self.raw['breakdowns'] = False
        return self

    def build(self):
        if self.report == DataWarehouseReport:
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
                raise InvalidReportError(response)

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
        if self.report == DataWarehouseReport:
            return self.suite.request('DataWarehouse', 'CancelRequest', {'Request_Id': self.id})
        else:
            return self.suite.request('Report', 'CancelReport', {'reportID': self.id})


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


def sync(queries, heartbeat=None, interval=1):
    for query in queries:
        query.queue()

    return [query.sync(heartbeat, interval) for query in queries]
