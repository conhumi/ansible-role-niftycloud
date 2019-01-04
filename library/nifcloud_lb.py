#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright 2017 FUJITSU CLOUD TECHNOLOGIES LIMITED
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import hashlib
import hmac
import time
import xml.etree.ElementTree as etree

import requests
from ansible.module_utils.basic import *  # noqa

try:
    # Python 2
    from urllib import quote, urlencode
except ImportError:
    # Python 3
    from urllib.parse import quote, urlencode

DOCUMENTATION = '''
---
module: nifcloud_lb
short_description: De-registers or registers an instance from Load Balancer in NIFCLOUD
description:
    - De-registers or registers an instance of NIFCLOUD from Load Balancer.
version_added: "0.1"
options:
    access_key:
        description:
            - Access key
        required: true
    secret_access_key:
        description:
            - Secret access key
        required: true
    endpoint:
        description:
            - API endpoint of target region.
        required: true
    loadbalancer_name:
        description:
            - Target Load Balancer name
        required: true
    loadbalancer_port:
        description:
            - Target Load Balancer port number
        required: true
    instance_port:
        description:
            - Destination port number
        required: true
    balancing_type:
        description:
            - Balancing type (1: Round-Robin or 2: Least-Connection)
        required: false
        default: 1
    network_volume:
        description:
            - Maximum of network volume
        required: false
        default: 10
    ip_version:
        description:
            - IP version (v4 or v6)
        required: false
        default: 'v4'
    accounting_type:
        description:
            - Accounting type (1: monthly, 2: pay per use)
        required: false
        default: 'v4'
    policy_type:
        description:
            - Encryption policy type (standard or ats)
        required: false
        default: 'standard'
    instance_ids:
        description:
            - List of Instance ID
        required: true
    purge_instance_ids:
        description:
            - Purge existing instance ids that are not found in instance_ids
        required: false
        default: true
    filter_ip_addresses:
        description:
            - List of ip addresses that allows/denys incoming communication to resources
        default: null
    filter_type:
        description:
            - Filter type that switch to allows/denys for filter ip addresses (1: allow or 2: deny)
        default: 1
    purge_filter_ip_addresses:
        description:
            - Purge existing filter ip addresses that are not found in filter_ip_addresses
        required: false
        default: true
    state:
        description:
            - Goal status (only "present")
        required: true
'''  # noqa

EXAMPLES = '''
- action: nifcloud_lb access_key="YOUR_ACCESS_KEY" secret_access_key="YOUR_SECRET_ACCESS_KEY" endpoint="west-1.cp.cloud.nifty.com" instance_id="test001" instance_port=80 loadbalancer_name="lb001" loadbalancer_port=80 state="present"
'''  # noqa


ISO8601 = '%Y-%m-%dT%H:%M:%SZ'


class LoadBalancerManager:
    """Handles NIFCLOUD LoadBalancer registration"""

    _ERROR_LB_NAME_NOT_FOUND = 'Client.InvalidParameterNotFound.LoadBalancer'
    _ERROR_LB_PORT_NOT_FOUND = 'Client.InvalidParameterNotFound.LoadBalancerPort'  # noqa

    def __init__(self, module):
        self.module = module

        self.access_key = module.params['access_key']
        self.secret_access_key = module.params['secret_access_key']
        self.endpoint = module.params['endpoint']

        self.loadbalancer_name = module.params['loadbalancer_name']
        self.loadbalancer_port = module.params['loadbalancer_port']
        self.instance_port = module.params['instance_port']
        self.balancing_type = module.params['balancing_type']
        self.network_volume = module.params['network_volume']
        self.ip_version = module.params['ip_version']
        self.accounting_type = module.params['accounting_type']
        self.policy_type = module.params['policy_type']

        self.instance_ids = module.params['instance_ids']
        self.purge_instance_ids = module.params['purge_instance_ids']
        self.filter_ip_addresses = module.params['filter_ip_addresses']
        self.filter_type = module.params['filter_type']
        self.purge_filter_ip_addresses = module.params['purge_filter_ip_addresses']  # noqa
        self.state = module.params['state']

        self.current_state = ''
        self.changed = False

    def ensure_present(self):
        self.current_state = self._get_state_instance_in_load_balancer()

        if self.current_state == 'absent':
            self._create_load_balancer()
        elif self.current_state == 'port-not-found':
            self._register_port()

        self._sync_filter()
        # self._regist_instance()

    def _describe_load_balancers(self, params):
        return request_to_api(self.module, 'GET', 'DescribeLoadBalancers',
                              params)

    def _describe_current_load_balancers(self):
        params = dict()
        params['LoadBalancerNames.member.1'] = self.loadbalancer_name
        params['LoadBalancerNames.LoadBalancerPort.1'] = self.loadbalancer_port
        params['LoadBalancerNames.InstancePort.1'] = self.instance_port
        return self._describe_load_balancers(params)

    def _get_state_instance_in_load_balancer(self):
        res = self._describe_current_load_balancers()

        if res['status'] == 200:
            return 'present'
        else:
            error_info = get_api_error(res['xml_body'])

            if error_info.get('code') == self._ERROR_LB_PORT_NOT_FOUND:
                return 'port-not-found'
            elif error_info.get('code') == self._ERROR_LB_NAME_NOT_FOUND:
                return 'absent'

            self._fail_request(res, 'check current state failed')

    def _is_present_in_load_balancer(self):
        return self._get_state_instance_in_load_balancer() == 'present'

    def _is_absent_in_load_balancer(self):
        return self._get_state_instance_in_load_balancer() == 'absent'

    def _create_load_balancer(self):
        params = dict()
        params['LoadBalancerName'] = self.loadbalancer_name
        params['Listeners.member.1.LoadBalancerPort'] = self.loadbalancer_port
        params['Listeners.member.1.InstancePort'] = self.instance_port
        params['Listeners.member.1.BalancingType'] = self.balancing_type
        params['NetworkVolume'] = self.network_volume
        params['IpVersion'] = self.ip_version
        params['AccountingType'] = self.accounting_type
        params['PolicyType'] = self.policy_type

        api_name = 'CreateLoadBalancer'
        res = request_to_api(self.module, 'POST', api_name, params)

        failed_msg = 'changes failed (create_load_balancer)'
        if res['status'] == 200:
            if self._wait_for_loadbalancer_status('present'):
                self.changed = True
            else:
                self._fail_request(res, failed_msg)
        else:
            self._fail_request(res, failed_msg)

    def _register_port(self):
        params = dict()
        params['LoadBalancerName'] = self.loadbalancer_name
        params['Listeners.member.1.LoadBalancerPort'] = self.loadbalancer_port
        params['Listeners.member.1.InstancePort'] = self.instance_port
        params['Listeners.member.1.BalancingType'] = self.balancing_type

        api_name = 'RegisterPortWithLoadBalancer'
        res = request_to_api(self.module, 'POST', api_name, params)

        failed_msg = 'changes failed (register_port)'
        if res['status'] == 200:
            if self._wait_for_loadbalancer_status('present'):
                self.changed = True
            else:
                self._fail_request(res, failed_msg)
        else:
            self._fail_request(res, failed_msg)

    def _wait_for_loadbalancer_status(self, goal_state):
        self.current_state = self._get_state_instance_in_load_balancer()

        if self.current_state == goal_state:
            return True

        retry_count = 10
        while retry_count > 0 and self.current_state != goal_state:
            time.sleep(60)
            self.current_state = self._get_state_instance_in_load_balancer()
            retry_count -= 1

        return self.current_state == goal_state

    def _regist_instance(self):
        if self._is_present_in_load_balancer():
            return (False, 'present')

        if self.module.check_mode:
            return (True, 'absent')

        params = dict()
        params['LoadBalancerName'] = self.loadbalancer_name
        params['LoadBalancerPort'] = self.loadbalancer_port
        params['InstancePort'] = self.instance_port

        instance_no = 1
        for instance_id in self.instance_ids:
            key = 'Instances.member.{0}.InstanceId'.format(instance_no)
            params[key] = instance_id
            instance_no = instance_no + 1

        res = request_to_api(self.module, 'GET',
                             'RegisterInstancesWithLoadBalancer', params)

        if res['status'] == 200:
            current_status = self._get_state_instance_in_load_balancer()
            return (True, current_status)
        else:
            error_info = get_api_error(res['xml_body'])
            self.module.fail_json(
                status=-1,
                msg='changes failed (regist_instance)',
                error_code=error_info.get('code'),
                error_message=error_info.get('message')
            )

    def _sync_filter(self):
        res = self._describe_current_load_balancers()

        current_filter_type = self._parse_filter_type(res)
        (purge_ip_list, merge_ip_list) = self._extract_filter_ip_diff(res)

        if (self.filter_type == current_filter_type) \
           and (len(purge_ip_list) == 0) and (len(merge_ip_list) == 0):
            return

        params = dict()
        params['LoadBalancerName'] = self.loadbalancer_name
        params['LoadBalancerPort'] = self.loadbalancer_port
        params['InstancePort'] = self.instance_port
        params['FilterType'] = self.filter_type

        ip_no = 1

        for ip in purge_ip_list:
            params['IPAddresses.member.{0}.IPAddress'.format(ip_no)] = ip
            addon_key = 'IPAddresses.member.{0}.AddOnFilter'.format(ip_no)
            params[addon_key] = 'false'
            ip_no = ip_no + 1

        for ip in merge_ip_list:
            params['IPAddresses.member.{0}.IPAddress'.format(ip_no)] = ip
            addon_key = 'IPAddresses.member.{0}.AddOnFilter'.format(ip_no)
            params[addon_key] = 'true'
            ip_no = ip_no + 1

        api_name = 'SetFilterForLoadBalancer'
        res = request_to_api(self.module, 'POST', api_name, params)

        if res['status'] == 200:
            self.changed = True
        else:
            self._fail_request(res, 'changes failed (set_filter)')

    def _parse_filter_type(self, res):
        filter_type = 1

        filter = res['xml_body'].find(
            './/{{{nc}}}Filter'.format(**res['xml_namespace']))

        if filter is not None:
            filter_type = int(filter.find(
                './/{{{nc}}}FilterType'.format(**res['xml_namespace'])).text)

        return filter_type

    def _extract_filter_ip_diff(self, res):
        filter_ip_list = []

        filter = res['xml_body'].find(
            './/{{{nc}}}Filter'.format(**res['xml_namespace']))

        if filter is not None:
            addresses_key = './/{{{nc}}}IPAddresses/{{{nc}}}member/{{{nc}}}IPAddress'.format(**res['xml_namespace'])  # noqa
            address_elements = filter.findall(addresses_key)
            filter_ip_list = [x.text for x in address_elements]

            # DescribeLoadBalancers returns ['*.*.*.*'] when none filter ip.
            filter_ip_list = [x for x in filter_ip_list if x != '*.*.*.*']

        purge_ip_list = []
        if self.purge_filter_ip_addresses:
            purge_ip_list = list(set(filter_ip_list) 
                                 - set(self.filter_ip_addresses))

        merge_ip_list = list(set(self.filter_ip_addresses)
                             - set(filter_ip_list))

        return (purge_ip_list, merge_ip_list)

    def _fail_request(self, response, msg):
        error_info = get_api_error(response['xml_body'])
        self.module.fail_json(
            status=-1,
            msg=msg,
            error_code=error_info.get('code'),
            error_message=error_info.get('message'),
        )


def calculate_signature(secret_access_key, method, endpoint, path, params):
    payload = ''
    for v in sorted(params.items()):
        payload += '&{0}={1}'.format(v[0], quote(str(v[1]), ''))
    payload = payload[1:]

    string_to_sign = [method, endpoint, path, payload]
    digest = hmac.new(
        secret_access_key.encode('utf-8'),
        '\n'.join(string_to_sign).encode('utf-8'),
        hashlib.sha256
    ).digest()

    return base64.b64encode(digest)


def request_to_api(module, method, action, params):
    params['Action'] = action
    params['AccessKeyId'] = module.params['access_key']
    params['SignatureMethod'] = 'HmacSHA256'
    params['SignatureVersion'] = '2'
    params['Timestamp'] = time.strftime(ISO8601, time.gmtime())

    path = '/api/'
    endpoint = module.params['endpoint']

    params['Signature'] = calculate_signature(
        module.params['secret_access_key'],
        method,
        endpoint,
        path,
        params
    )

    r = None
    if method == 'GET':
        url = 'https://{0}{1}?{2}'.format(endpoint, path,
                                          urlencode(params))
        r = requests.get(url)
    elif method == 'POST':
        url = 'https://{0}{1}'.format(endpoint, path)
        r = requests.post(url, urlencode(params))
    else:
        module.fail_json(
            status=-1,
            msg='changes failed (un-supported http method)'
        )

    if r is not None:
        body = r.text.encode('utf-8')
        xml = etree.fromstring(body)
        info = dict(
            status=r.status_code,
            xml_body=xml,
            xml_namespace=dict(nc=xml.tag[1:].split('}')[0])
        )
        return info
    else:
        module.fail_json(status=-1, msg='changes failed (http request failed)')


def get_api_error(xml_body):
    info = dict(
        code=xml_body.find('.//Errors/Error/Code').text,
        message=xml_body.find('.//Errors/Error/Message').text
    )
    return info


def main():
    module = AnsibleModule(  # noqa
        argument_spec=dict(
            access_key=dict(required=True,  type='str'),
            secret_access_key=dict(required=True,  type='str', no_log=True),
            endpoint=dict(required=True,  type='str'),
            loadbalancer_name=dict(required=True, type='str'),
            loadbalancer_port=dict(required=True, type='int'),
            instance_port=dict(required=True, type='int'),
            balancing_type=dict(required=False, type='int', default=1),
            network_volume=dict(required=False, type='int', default=10),
            ip_version=dict(required=False, type='str', default='v4'),
            accounting_type=dict(required=False, type='str', default='1'),
            policy_type=dict(equired=False, type='str', default='standard'),
            instance_ids=dict(required=False,  type='list', default=list()),
            purge_instance_ids=dict(required=False, type='bool',
                                    default=True),
            filter_ip_addresses=dict(required=False, type='list',
                                     default=list()),
            filter_type=dict(required=False, type='int', default=1),
            purge_filter_ip_addresses=dict(required=False, type='bool',
                                           default=True),
            state=dict(required=True,  type='str'),
        ),
        supports_check_mode=True
    )

    goal_state = module.params['state']

    manager = LoadBalancerManager(module)

    if goal_state == 'present':
        manager.ensure_present()
    else:
        module.fail_json(
            status=-1,
            msg='invalid state (goal state = "{0}")'.format(goal_state)
        )

    module.exit_json(
        changed=manager.changed,
        loadbalancer_name=manager.loadbalancer_name,
        status=manager.current_state,
    )


if __name__ == '__main__':
    main()
