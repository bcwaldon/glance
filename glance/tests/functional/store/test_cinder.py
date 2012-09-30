# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack, LLC
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
Functional tests for the Swift store interface

Set the GLANCE_TEST_SWIFT_CONF environment variable to the location
of a Glance config that defines how to connect to a functional
Swift backend
"""

import ConfigParser
import unittest

import glance.openstack.common.cfg
import glance.store.cinder
import glance.tests.functional.store as store_tests

try:
    import cinderclient.v1.client as cinder_v1
except ImportError:
    cinder_v1 = None


class CinderStoreError(RuntimeError):
    pass


def read_config(path):
    cp = ConfigParser.RawConfigParser()
    cp.read(path)
    return cp


def parse_config(config):
    out = {}
    options = [
    ]

    for option in options:
        out[option] = config.defaults()[option]

    return out


def keystone_authenticate(auth_url, tenant_id, username, password):
    import keystoneclient.v2_0.client
    ksclient = keystoneclient.v2_0.client.Client(tenant_id=tenant_id,
                                                 username=username,
                                                 password=password,
                                                 auth_url=auth_url)

    auth_resp = ksclient.service_catalog.catalog
    tenant_id = auth_resp['token']['tenant']['id']
    service_catalog = auth_resp['serviceCatalog']
    return tenant_id, ksclient.auth_token, service_catalog


class TestCinderStore(store_tests.BaseTestCase, unittest.TestCase):

    store_cls = glance.store.cinder.Store
    store_name = 'cinder'

    auth_url = 'http://devstack:5000/v2.0'
    tenant_id = 'da07472a979c42de86e03af9129560e9'
    username = 'admin'
    password = 'secrete'

    def setUp(self):
        super(TestCinderStore, self).setUp()

    def get_store(self, **kwargs):
        tenant_id, auth_token, svc_catalog = keystone_authenticate(
                self.auth_url, self.tenant_id, self.username, self.password)
        context = glance.context.RequestContext(auth_tok=auth_token,
                                                tenant=tenant_id,
                                                service_catalog=svc_catalog)
        store = glance.store.cinder.Store(context=context)
        store.configure()
        store.configure_add()
        return store

    def get_default_store_specs(self, image_id):
        return {}

    def stash_image(self, image_id, image_data):
        cinder_client = cinder_v1.Client(self.username,
                                         self.password,
                                         tenant_id=self.tenant_id,
                                         auth_url=self.auth_url)
        cinder_client.volumes.list()

