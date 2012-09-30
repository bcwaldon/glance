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

from glance.openstack.common import cfg
import glance.openstack.common.log as logging
import glance.store
import glance.store.base
import glance.store.location

try:
    import cinderclient.v1.client as cinder_client
except ImportError:
    pass

LOG = logging.getLogger(__name__)

cinder_opts = [
    #cfg.StrOpt('swift_store_auth_address'),
]

CONF = cfg.CONF
CONF.register_opts(cinder_opts)


class StoreLocation(glance.store.location.StoreLocation):
    """
    Class describing a Cinder URI. A Cinder URI can look like any of
    the following:

        cinder://<VOLUME_ID>
    """

    def process_specs(self):
        self.volume_id = self.specs['volume_id']

    def get_uri(self):
        return 'cinder://%s' % self.volume_id

    def parse_uri(self, uri):
        self.volume_id = uri.split('://')[1]


class Store(glance.store.base.Store):
    """An implementation of the swift backend adapter."""

    def get_schemes(self):
        return ('cinder',)

    def configure(self):
        pass

    def configure_add(self):
        pass

    def get(self, location):
        volume_id = location.store_location.volume_id
        client = self._get_client()
        volume = client.volumes.get(volume_id)

        class ChunkIterator(object):
            def __init__(self, fd):
                self.fd = fd

            def __iter__(self):
                return self

            def _get_chunk(self):
                return self.fd.read(65536)

            def next(self):
                chunk = self._get_chunk()
                if chunk:
                    return chunk
                else:
                    raise StopIteration


        volume_file = volume.read()
        volume_size_bytes = volume.size*1024*1024*1024
        return (ChunkIterator(volume_file), volume_size_bytes)

    def get_size(self, location):
        volume_id = location.store_location.volume_id
        client = self._get_client()
        volume = client.volumes.get(volume_id)
        return volume.size*1024*1024*1024

    def _get_client(self):
        for service in self.context.service_catalog:
            if service['type'] == 'volume':
                endpoint = service['endpoints'][0]['publicURL']
                break
        else:
            raise Exception('No volume endpoint found')

        return cinder_client.Client(None, None, proxy_tenant_id=self.context.tenant, proxy_token=self.context.auth_tok, auth_url='http://localhost:5000/v2.0')

    def add(self, image_id, image_file, image_size):
        client = self._get_client()
        size_in_gb = (image_size/1024.0/1024.0/1024) + 1
        name = 'image-%s' % image_id
        volume = client.volumes.create(size_in_gb, display_name=name)
        import time
        time.sleep(10)
        volume.write(image_file)

        location = StoreLocation({'volume_id': volume.id})
        return (location.get_uri(), size_in_gb*1024*1024*1024, None)

    def delete(self, location):
        client = self._get_client()
        client.volumes.delete(location.store_location.volume_id)

    def set_acls(self, location, public=False, read_tenants=[],
                     write_tenants=[]):
        return None
