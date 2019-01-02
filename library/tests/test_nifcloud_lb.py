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

import copy
import sys
import time
import unittest
import xml.etree.ElementTree as etree

import mock
import nifcloud_lb

sys.path.append('.')
sys.path.append('..')


class TestNifcloud(unittest.TestCase):
    TARGET_PRESENT_LB = 'nifcloud_lb.LoadBalancerManager._is_present_in_load_balancer'  # noqa
    TARGET_WAIT_LB_STATUS = 'nifcloud_lb.LoadBalancerManager._wait_for_loadbalancer_status'  # noqa

    def setUp(self):
        self.mockModule = mock.MagicMock(
            params=dict(
                access_key='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                secret_access_key='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                endpoint='west-1.cp.cloud.nifty.com',
                loadbalancer_name='lb001',
                loadbalancer_port=80,
                instance_port=80,
                balancing_type=1,
                network_volume=10,
                ip_version='v4',
                accounting_type='1',
                policy_type='standard',
                instance_ids=['test001'],
                purge_instance_ids=True,
                filter_ip_addresses=['192.168.0.1', '192.168.0.2'],
                filter_type=1,
                purge_filter_ip_addresses=True,
                state='present'
            ),
            fail_json=mock.MagicMock(side_effect=Exception('failed')),
            check_mode=False,
        )

        self.xmlnamespace = 'https://cp.cloud.nifty.com/api/'
        self.xml = nifcloud_api_response_sample

        self.mockRequestsGetDescribeLoadBalancers = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=200,
                text=self.xml['describeLoadBalancers']
            ))

        self.mockRequestsGetDescribeLoadBalancersNameNotFound = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=500,
                text=self.xml['describeLoadBalancersNameNotFound']
            ))

        self.mockRequestsGetDescribeLoadBalancersPortNotFound = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=500,
                text=self.xml['describeLoadBalancersPortNotFound']
            ))

        self.mockDescribeLoadBalancers = mock.MagicMock(
            return_value=dict(
                status=200,
                xml_body=etree.fromstring(self.xml['describeLoadBalancers']),
                xml_namespace=dict(nc=self.xmlnamespace)
            ))

        self.mockRequestsPostCreateLoadBalancer = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=200,
                text=self.xml['createLoadBalancer']
            ))

        self.mockRequestsPostRegisterPortWithLoadBalancer = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=200,
                text=self.xml['registerPortWithLoadBalancer']
            ))

        self.mockRequestsGetRegisterInstancesWithLoadBalancer = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=200,
                text=self.xml['registerInstancesWithLoadBalancer']
            ))

        self.mockRequestsGetDeregisterInstancesFromLoadBalancer = mock.MagicMock(  # noqa
            return_value=mock.MagicMock(
                status_code=200,
                text=self.xml['deregisterInstancesFromLoadBalancer']
            ))

        self.mockRequestsInternalServerError = mock.MagicMock(
            return_value=mock.MagicMock(
                status_code=500,
                text=self.xml['internalServerError']
            ))

        self.mockRequestsError = mock.MagicMock(return_value=None)
        self.mockGmtime = mock.MagicMock(return_value=time.gmtime(0))

        patcher = mock.patch('time.sleep')
        self.addCleanup(patcher.stop)
        self.mock_time_sleep = patcher.start()

    # calculate signature
    def test_calculate_signature(self):
        secret_access_key = self.mockModule.params['secret_access_key']
        method = 'GET'
        endpoint = self.mockModule.params['endpoint']
        path = '/api/'
        params = dict(
            Action='DescribeLoadBalancers',
            AccessKeyId=self.mockModule.params['access_key'],
            SignatureMethod='HmacSHA256',
            SignatureVersion='2',
        )

        with mock.patch('time.gmtime', self.mockGmtime):
            signature = nifcloud_lb.calculate_signature(
                secret_access_key,
                method,
                endpoint,
                path,
                params
            )
            self.assertEqual(signature,
                             b'spq6n8gdx5j17CnUXsR2U5OdehAHs1jJMJ42kiGnZMw=')

    # calculate signature with string parameter including slash
    def test_calculate_signature_with_slash(self):
        secret_access_key = self.mockModule.params['secret_access_key']
        method = 'GET'
        endpoint = self.mockModule.params['endpoint']
        path = '/api/'
        params = dict(
            Action='DescribeLoadBalancers',
            AccessKeyId=self.mockModule.params['access_key'],
            SignatureMethod='HmacSHA256',
            SignatureVersion='2',
            Description='/'
        )

        signature = nifcloud_lb.calculate_signature(
            secret_access_key,
            method,
            endpoint,
            path,
            params
        )

        # This constant string is signature calculated by
        # "library/tests/files/calculate_signature_sample.sh".
        # This shell-script calculate with encoding a slash,
        # like "nifcloud.calculate_signature()".
        self.assertEqual(signature,
                         b'xDRKZSHLjnS1fW5xBMZoZD5T+tQ7Hk3A3ZXWT4HuNnM=')

    # method get
    def test_request_to_api_get(self):
        method = 'GET'
        action = 'DescribeLoadBalancers'
        params = dict()

        with mock.patch('requests.get',
                        self.mockRequestsGetDescribeLoadBalancers):
            info = nifcloud_lb.request_to_api(self.mockModule, method,
                                              action, params)

        self.assertEqual(info['status'], 200)
        self.assertEqual(info['xml_namespace'], dict(nc=self.xmlnamespace))
        self.assertEqual(
            etree.tostring(info['xml_body']),
            etree.tostring(etree.fromstring(self.xml['describeLoadBalancers']))
        )

    # api error
    def test_request_to_api_error(self):
        method = 'GET'
        action = 'DescribeLoadBalancers'
        params = dict()

        with mock.patch('requests.get', self.mockRequestsInternalServerError):
            info = nifcloud_lb.request_to_api(self.mockModule, method,
                                              action, params)

        self.assertEqual(info['status'], 500)
        self.assertEqual(
            etree.tostring(info['xml_body']),
            etree.tostring(etree.fromstring(self.xml['internalServerError']))
        )

    # method failed
    def test_request_to_api_unknown(self):
        method = 'UNKNOWN'
        action = 'DescribeLoadBalancers'
        params = dict()

        self.assertRaises(
            Exception,
            nifcloud_lb.request_to_api,
            (self.mockModule, method, action, params)
        )

    # network error
    def test_request_to_api_request_error(self):
        method = 'GET'
        action = 'DescribeLoadBalancers'
        params = dict()

        with mock.patch('requests.get', self.mockRequestsError):
            self.assertRaises(
                Exception,
                nifcloud_lb.request_to_api,
                (self.mockModule, method, action, params)
            )

    # get api error code & message
    def test_get_api_error(self):
        method = 'GET'
        action = 'DescribeLoadBalancers'
        params = dict()

        with mock.patch('requests.get', self.mockRequestsInternalServerError):
            info = nifcloud_lb.request_to_api(self.mockModule, method,
                                              action, params)

        error_info = nifcloud_lb.get_api_error(info['xml_body'])
        self.assertEqual(error_info['code'],    'Server.InternalError')
        self.assertEqual(error_info['message'],
                         'An error has occurred. Please try again later.')

    # describe
    def test_describe_load_balancers(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetDescribeLoadBalancers):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            info = manager._describe_load_balancers(dict())
        self.assertEqual(info['status'], 200)
        self.assertEqual(info['xml_namespace'], dict(nc=self.xmlnamespace))
        self.assertEqual(
            etree.tostring(info['xml_body']),
            etree.tostring(etree.fromstring(self.xml['describeLoadBalancers']))
        )

    # present
    def test_get_state_instance_in_load_balancer_present(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetDescribeLoadBalancers):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertEqual(
                'present',
                manager._get_state_instance_in_load_balancer()
            )

    # port-not-found
    def test_get_state_instance_in_load_balancer_port_not_found(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetDescribeLoadBalancersPortNotFound):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertEqual(
                'port-not-found',
                manager._get_state_instance_in_load_balancer()
            )

    # absent
    def test_get_state_instance_in_load_balancer_absent(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetDescribeLoadBalancersNameNotFound):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertEqual(
                'absent',
                manager._get_state_instance_in_load_balancer()
            )

    # internal server error
    def test_get_state_instance_in_load_balancer_error(self):
        with mock.patch('requests.get', self.mockRequestsInternalServerError):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertRaises(
                Exception,
                manager._get_state_instance_in_load_balancer,
            )

    # is present load balancer (present)
    def test_is_present_in_load_balancer_present(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetDescribeLoadBalancers):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertEqual(
                True,
                manager._is_present_in_load_balancer()
            )

    # is present load balancer (absent)
    def test_is_present_in_load_balancer_absent(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetDescribeLoadBalancersNameNotFound):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertEqual(
                False,
                manager._is_present_in_load_balancer()
            )

    # internal server error
    def test_is_present_in_load_balancer_error(self):
        with mock.patch('requests.get', self.mockRequestsInternalServerError):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertRaises(
                Exception,
                manager._is_present_in_load_balancer,
            )

    # is absent load balancer (present)
    def test_is_absent_in_load_balancer_present(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetDescribeLoadBalancers):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertEqual(
                False,
                manager._is_absent_in_load_balancer()
            )

    # is absent load balancer (absent)
    def test_is_absent_in_load_balancer_absent(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetDescribeLoadBalancersNameNotFound):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertEqual(
                True,
                manager._is_absent_in_load_balancer()
            )

    # internal server error
    def test_is_absent_in_load_balancer_error(self):
        with mock.patch('requests.get', self.mockRequestsInternalServerError):
            manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertRaises(
                Exception,
                manager._is_absent_in_load_balancer,
            )

    # _create_loadbalancer success
    def test_create_loadbalancer_success(self):
        with mock.patch('requests.post',
                        self.mockRequestsPostCreateLoadBalancer):

            with mock.patch(self.TARGET_WAIT_LB_STATUS,
                            mock.MagicMock(return_value=True)):
                manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
                manager._create_load_balancer()
                self.assertEqual(True, manager.changed)

    # _create_loadbalancer wait failed
    def test_create_loadbalancer_wait_failed(self):
        with mock.patch('requests.post',
                        self.mockRequestsPostCreateLoadBalancer):

            with mock.patch(self.TARGET_WAIT_LB_STATUS,
                            mock.MagicMock(return_value=False)):
                manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertRaises(
                Exception,
                manager._create_load_balancer,
            )

    # _create_loadbalancer internal error
    def test_create_loadbalancer_internal_error(self):
        with mock.patch('requests.post',
                        self.mockRequestsInternalServerError):

            with mock.patch(self.TARGET_WAIT_LB_STATUS,
                            mock.MagicMock(return_value=False)):
                manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertRaises(
                Exception,
                manager._create_load_balancer,
            )

    # _register_port success
    def test_register_port_success(self):
        with mock.patch('requests.post',
                        self.mockRequestsPostRegisterPortWithLoadBalancer):

            with mock.patch(self.TARGET_WAIT_LB_STATUS,
                            mock.MagicMock(return_value=True)):
                manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
                manager._register_port()
                self.assertEqual(True, manager.changed)

    # _register_port wait failed
    def test_register_port_wait_failed(self):
        with mock.patch('requests.post',
                        self.mockRequestsPostRegisterPortWithLoadBalancer):

            with mock.patch(self.TARGET_WAIT_LB_STATUS,
                            mock.MagicMock(return_value=False)):
                manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertRaises(
                Exception,
                manager._register_port,
            )

    # _register_port internal error
    def test_register_port_internal_error(self):
        with mock.patch('requests.post',
                        self.mockRequestsInternalServerError):

            with mock.patch(self.TARGET_WAIT_LB_STATUS,
                            mock.MagicMock(return_value=False)):
                manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
            self.assertRaises(
                Exception,
                manager._register_port,
            )

    # absent -> present
    def test_regist_instance_absent(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetRegisterInstancesWithLoadBalancer):

            with mock.patch(self.TARGET_PRESENT_LB,
                            mock.MagicMock(return_value=False)):
                manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
                self.assertEqual(
                    (True, 'present'),
                    manager._regist_instance()
                )

    # present -> present
    def test_regist_instance_present(self):
        with mock.patch('requests.get',
                        self.mockRequestsGetRegisterInstancesWithLoadBalancer):
            with mock.patch(self.TARGET_PRESENT_LB,
                            mock.MagicMock(return_value=True)):
                manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
                self.assertEqual(
                    (False, 'present'),
                    manager._regist_instance()
                )

    # absent -> present (check mode)
    def test_regist_instance_check_mode(self):
        mockModule = mock.MagicMock(
            params=copy.deepcopy(self.mockModule.params),
            check_mode=True,
        )
        manager = nifcloud_lb.LoadBalancerManager(mockModule)
        self.assertEqual(
            (True, 'absent'),
            manager._regist_instance()
        )

    # internal server error
    def test_regist_instance_error(self):
        with mock.patch('requests.get', self.mockRequestsInternalServerError):
            with mock.patch(self.TARGET_PRESENT_LB,
                            mock.MagicMock(return_value=False)):
                manager = nifcloud_lb.LoadBalancerManager(self.mockModule)
                self.assertRaises(
                    Exception,
                    manager._regist_instance,
                    (self.mockModule)
                )


nifcloud_api_response_sample = dict(
    describeLoadBalancers='''
<DescribeLoadBalancersResponse xmlns="https://cp.cloud.nifty.com/api/">
<DescribeLoadBalancersResult>
 <LoadBalancerDescriptions>
  <member>
  <LoadBalancerName>lb000</LoadBalancerName>
  <DNSName>111.171.200.1</DNSName>
  <NetworkVolume>10</NetworkVolume>
  <ListenerDescriptions>
   <member>
   <Listener>
    <Protocol>HTTP</Protocol>
    <LoadBalancerPort>80</LoadBalancerPort>
    <InstancePort>80</InstancePort>
    <balancingType>1</balancingType>
    <SSLCertificateId>100</SSLCertificateId>
   </Listener>
   </member>
  </ListenerDescriptions>
  <Policies>
   <AppCookieStickinessPolicies>
    <member>
     <PolicyName/>
     <CookieName/>
    </member>
   </AppCookieStickinessPolicies>
   <LBCookieStickinessPolicies>
    <member>
     <PolicyName/>
     <CookieExpirationPeriod/>
    </member>
   </LBCookieStickinessPolicies>
  </Policies>
  <AvailabilityZones>
   <member>east-11</member>
  </AvailabilityZones>
  <Instances>
  </Instances>
  <HealthCheck>
   <Target>TCP:80</Target>
   <Interval>300</Interval>
   <Timeout>900</Timeout>
   <UnhealthyThreshold>3</UnhealthyThreshold>
   <HealthyThreshold>1</HealthyThreshold>
  </HealthCheck>
  <Filter>
   <FilterType>1</FilterType>
   <IPAddresses>
    <member>
     <IPAddress>192.168.0.1</IPAddress>
     <IPAddress>192.168.0.2</IPAddress>
    </member>
   </IPAddresses>
  </Filter>
  <CreatedTime>2010-05-17T11:22:33.456Z</CreatedTime>
  <AccountingType>1</AccountingType>
  <NextMonthAccountingType>1</NextMonthAccountingType>
  <Option>
    <SessionStickinessPolicy>
      <Enabled>true</Enabled>
      <ExpirationPeriod>10</ExpirationPeriod>
    </SessionStickinessPolicy>
    <SorryPage>
      <Enabled>true</Enabled>
      <StatusCode>200</StatusCode>
    </SorryPage>
  </Option>
  </member>
  <member>
  <LoadBalancerName>lb001</LoadBalancerName>
  <DNSName>111.171.200.1</DNSName>
  <NetworkVolume>10</NetworkVolume>
  <ListenerDescriptions>
   <member>
   <Listener>
    <Protocol>HTTP</Protocol>
    <LoadBalancerPort>80</LoadBalancerPort>
    <InstancePort>80</InstancePort>
    <balancingType>1</balancingType>
    <SSLCertificateId>100</SSLCertificateId>
   </Listener>
   </member>
  </ListenerDescriptions>
  <Policies>
   <AppCookieStickinessPolicies>
    <member>
     <PolicyName/>
     <CookieName/>
    </member>
   </AppCookieStickinessPolicies>
   <LBCookieStickinessPolicies>
    <member>
     <PolicyName/>
     <CookieExpirationPeriod/>
    </member>
   </LBCookieStickinessPolicies>
  </Policies>
  <AvailabilityZones>
   <member>east-11</member>
  </AvailabilityZones>
  <Instances>
   <member>
   <InstanceId>test001</InstanceId>
   <InstanceUniqueId>i-asdg1234</InstanceUniqueId>
   </member>
  </Instances>
  <HealthCheck>
   <Target>TCP:80</Target>
   <Interval>300</Interval>
   <Timeout>900</Timeout>
   <UnhealthyThreshold>3</UnhealthyThreshold>
   <HealthyThreshold>1</HealthyThreshold>
   <InstanceStates>
    <member>
     <InstanceId>Server001</InstanceId>
     <InstanceUniqueId>i-12345678</InstanceUniqueId>
     <State>InService</State>
     <ResponseCode />
     <Description />
    </member>
   </InstanceStates>
  </HealthCheck>
  <Filter>
   <FilterType>1</FilterType>
   <IPAddresses>
    <member>
     <IPAddress>111.111.111.111</IPAddress>
     <IPAddress>111.111.111.112</IPAddress>
    </member>
   </IPAddresses>
  </Filter>
  <CreatedTime>2010-05-17T11:22:33.456Z</CreatedTime>
  <AccountingType>1</AccountingType>
  <NextMonthAccountingType>1</NextMonthAccountingType>
  <Option>
    <SessionStickinessPolicy>
      <Enabled>true</Enabled>
      <ExpirationPeriod>10</ExpirationPeriod>
    </SessionStickinessPolicy>
    <SorryPage>
      <Enabled>true</Enabled>
      <StatusCode>200</StatusCode>
    </SorryPage>
  </Option>
  </member>
 </LoadBalancerDescriptions>
 </DescribeLoadBalancersResult>
  <ResponseMetadata>
    <RequestId>f6dd8353-eb6b-6b4fd32e4f05</RequestId>
  </ResponseMetadata>
</DescribeLoadBalancersResponse>
''',
    describeLoadBalancersNameNotFound='''
<Response>
 <Errors>
  <Error>
   <Code>Client.InvalidParameterNotFound.LoadBalancer</Code>
   <Message>The LoadBalancerName 'lb001' does not exist.</Message>
  </Error>
 </Errors>
 <RequestID>5ec8da0a-6e23-4343-b474-ca0bb5c22a51</RequestID>
</Response>
''',
    describeLoadBalancersPortNotFound='''
<Response>
 <Errors>
  <Error>
   <Code>Client.InvalidParameterNotFound.LoadBalancerPort</Code>
   <Message>The requested LoadBalancer 'lb001' does not have this port (loadBalancerPort:80,instancePort:80).</Message>
  </Error>
 </Errors>
 <RequestID>5ec8da0a-6e23-4343-b474-ca0bb5c22a51</RequestID>
</Response>
''',  # noqa
    registerInstancesWithLoadBalancer='''
<RegisterInstancesWithLoadBalancerResponse xmlns="https://cp.cloud.nifty.com/api/">
  <RegisterInstancesWithLoadBalancerResult>
    <Instances>
      <member>
        <InstanceId>test001</InstanceId>
        <instanceUniqueId>i-asda1234</instanceUniqueId>
      </member>
    </Instances>
  </RegisterInstancesWithLoadBalancerResult>
  <ResponseMetadata>
    <RequestId>f6dd8353-eb6b-6b4fd32e4f05</RequestId>
  </ResponseMetadata>
</RegisterInstancesWithLoadBalancerResponse>
''',  # noqa
    createLoadBalancer='''
<CreateLoadBalancerResponse xmlns="https://cp.cloud.nifty.com/api/">
  <CreateLoadBalancerResult>
    <DNSName>111.171.200.1</DNSName>
  </CreateLoadBalancerResult>
  <ResponseMetadata>
    <RequestId>ac501097-4c8d-475b-b06b-a90048ec181c</RequestId>
  </ResponseMetadata>
</CreateLoadBalancerResponse>
''',
    registerPortWithLoadBalancer='''
<RegisterPortWithLoadBalancerResponse xmlns="https://cp.cloud.nifty.com/api/">
  <RegisterPortWithLoadBalancerResult>
    <Listeners>
      <member>
        <Protocol>HTTP</Protocol>
        <LoadBalancerPort>80</LoadBalancerPort>
        <InstancePort>80</InstancePort>
        <BalancingType>1</BalancingType>
      </member>
    </Listeners>
  </RegisterPortWithLoadBalancerResult>
  <ResponseMetadata>
    <RequestId>ac501097-4c8d-475b-b06b-a90048ec181c</RequestId>
  </ResponseMetadata>
</RegisterPortWithLoadBalancerResponse>
''',
    deregisterInstancesFromLoadBalancer='''
<DeregisterInstancesFromLoadBalancerResponse xmlns="https://cp.cloud.nifty.com/api/">
  <DeregisterInstancesFromLoadBalancerResult>
    <Instances>
      <member>
        <InstanceId>test001</InstanceId>
        <instanceUniqueId>i-abvf1234</instanceUniqueId>
      </member>
    </Instances>
  </DeregisterInstancesFromLoadBalancerResult>
  <ResponseMetadata>
    <RequestId>f6dd8353-eb6b-6b4fd32e4f05</RequestId>
  </ResponseMetadata>
</DeregisterInstancesFromLoadBalancerResponse>
''',  # noqa
    internalServerError='''
<Response>
 <Errors>
  <Error>
   <Code>Server.InternalError</Code>
   <Message>An error has occurred. Please try again later.</Message>
  </Error>
 </Errors>
 <RequestID>5ec8da0a-6e23-4343-b474-ca0bb5c22a51</RequestID>
</Response>
'''
)

if __name__ == '__main__':
    unittest.main()
