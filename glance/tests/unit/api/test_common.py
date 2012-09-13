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

import unittest

import mox

import glance.api.common
from glance.common import exception
from glance.common import utils
import glance.context


class SimpleIterator(object):
    def __init__(self, file_object, chunk_size):
        self.file_object = file_object
        self.chunk_size = chunk_size

    def __iter__(self):
        def read_chunk():
            return self.fobj.read(self.chunk_size)

        chunk = read_chunk()
        while chunk:
            yield chunk
            chunk = read_chunk()
        else:
            raise StopIteration()


class TestSizeCheckedIter(unittest.TestCase):
    def setUp(self):
        self.image_id = 'e31cb99c-fe89-49fb-9cc5-f5104fffa636'
        self.notify_cb = lambda *args: None

    def test_uniform_chunk_size(self):
        checked_image = glance.api.common.size_checked_iter(
                self.image_id, 4, ['AB', 'CD'], self.notify_cb)

        self.assertEqual('AB', checked_image.next())
        self.assertEqual('CD', checked_image.next())
        self.assertRaises(StopIteration, checked_image.next)

    def test_small_last_chunk(self):
        checked_image = glance.api.common.size_checked_iter(
                self.image_id, 3, ['AB', 'C'], self.notify_cb)

        self.assertEqual('AB', checked_image.next())
        self.assertEqual('C', checked_image.next())
        self.assertRaises(StopIteration, checked_image.next)

    def test_variable_chunk_size(self):
        checked_image = glance.api.common.size_checked_iter(
                self.image_id, 6, ['AB', '', 'CDE', 'F'], self.notify_cb)

        self.assertEqual('AB', checked_image.next())
        self.assertEqual('', checked_image.next())
        self.assertEqual('CDE', checked_image.next())
        self.assertEqual('F', checked_image.next())
        self.assertRaises(StopIteration, checked_image.next)

    def test_too_many_chunks(self):
        """An image should streamed regardless of expected_size"""
        checked_image = glance.api.common.size_checked_iter(
                self.image_id, 4, ['AB', 'CD', 'EF'], self.notify_cb)

        self.assertEqual('AB', checked_image.next())
        self.assertEqual('CD', checked_image.next())
        self.assertEqual('EF', checked_image.next())
        self.assertRaises(exception.GlanceException, checked_image.next)

    def test_too_few_chunks(self):
        checked_image = glance.api.common.size_checked_iter(
                 self.image_id, 6, ['AB', 'CD'], self.notify_cb)

        self.assertEqual('AB', checked_image.next())
        self.assertEqual('CD', checked_image.next())
        self.assertRaises(exception.GlanceException, checked_image.next)

    def test_too_much_data(self):
        checked_image = glance.api.common.size_checked_iter(
                 self.image_id, 3, ['AB', 'CD'], self.notify_cb)

        self.assertEqual('AB', checked_image.next())
        self.assertEqual('CD', checked_image.next())
        self.assertRaises(exception.GlanceException, checked_image.next)

    def test_too_little_data(self):
        checked_image = glance.api.common.size_checked_iter(
                 self.image_id, 6, ['AB', 'CD', 'E'], self.notify_cb)

        self.assertEqual('AB', checked_image.next())
        self.assertEqual('CD', checked_image.next())
        self.assertEqual('E', checked_image.next())
        self.assertRaises(exception.GlanceException, checked_image.next)

    def test_calls_notify_cb(self):
        m = mox.Mox()
        notify_cb = m.CreateMockAnything()
        notify_cb(5)
        checked_image = glance.api.common.size_checked_iter(
                 self.image_id, 5, ['AB', 'CD', 'E'], notify_cb)
        m.ReplayAll()
        list(checked_image)
        m.VerifyAll()

    def test_calls_notify_cb_write_mismatch(self):
        """Assert notify_cb is called when unexpected bytes are written"""
        m = mox.Mox()
        notify_cb = m.CreateMockAnything()
        notify_cb(5)
        checked_image = glance.api.common.size_checked_iter(
                 self.image_id, 6, ['AB', 'CD', 'E'], notify_cb)
        m.ReplayAll()
        self.assertRaises(exception.GlanceException, list, checked_image)
        m.VerifyAll()


class TestImageSendNotification(unittest.TestCase):
    def setUp(self):
        self.image_id = utils.generate_uuid()
        self.image_owner = utils.generate_uuid()
        self.image_meta = {'id': self.image_id, 'owner': self.image_owner}
        user_id = utils.generate_uuid()
        tenant_id = utils.generate_uuid()
        self.context = glance.context.RequestContext(user=user_id,
                                                     tenant=tenant_id)

    def test_image_send_notification(self):
        expected_payload = {
            'bytes_sent': 19,
            'image_id': self.image_meta['id'],
            'owner_id': self.image_meta['owner'],
            'receiver_tenant_id': self.context.tenant,
            'receiver_user_id': self.context.user,
            'destination_ip': '1.2.3.4',
            }

        m = mox.Mox()
        notifier = m.CreateMockAnything()
        notifier.info('image.send', expected_payload)
        m.ReplayAll()
        glance.api.common.image_send_notification(
                notifier, self.context, 19, 19, self.image_meta, '1.2.3.4')
        m.VerifyAll()
        m.ResetAll()

    def test_image_send_notification_bytes_sent_error(self):
        """Ensure image.send notification is sent on error."""
        expected_payload = {
            'bytes_sent': 17,
            'image_id': self.image_meta['id'],
            'owner_id': self.image_meta['owner'],
            'receiver_tenant_id': self.context.tenant,
            'receiver_user_id': self.context.user,
            'destination_ip': '1.2.3.4',
            }

        m = mox.Mox()
        notifier = m.CreateMockAnything()
        notifier.error('image.send', expected_payload)
        m.ReplayAll()
        glance.api.common.image_send_notification(
                notifier, self.context, 17, 19, self.image_meta, '1.2.3.4')
        m.VerifyAll()
        m.ResetAll()

    def test_get_image_send_notify_cb(self):
        context = glance.context.RequestContext()
        image_meta = {'id': utils.generate_uuid()}
        m = mox.Mox()
        m.StubOutWithMock(glance.api.common, 'image_send_notification')
        glance.api.common.image_send_notification(
                None, context, 12, 10, image_meta, '4.3.2.1')
        m.ReplayAll()
        notify_cb = glance.api.common.get_image_send_notify_cb(
                context, image_meta, 10, None, '4.3.2.1')
        notify_cb(12)
        m.VerifyAll()

