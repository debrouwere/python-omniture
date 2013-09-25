import requests
import binascii
import time
import sha
import json
from datetime import datetime
from elements import Value, Element, Segment
from query import Query
import utils

# encoding: utf-8

class Account(object):
    DEFAULT_ENDPOINT = 'https://api.omniture.com/admin/1.3/rest/'

    def __init__(self, username, secret, endpoint=DEFAULT_ENDPOINT):
        self.username = username
        self.secret = secret
        self.endpoint = endpoint
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

