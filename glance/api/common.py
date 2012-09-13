# Copyright 2012 OpenStack LLC.
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

from glance.common import exception
from glance.openstack.common import log as logging

LOG = logging.getLogger(__name__)


def size_checked_iter(image_id, expected_size, image_iter, notify_cb):
    bytes_written = 0
    try:
        for chunk in image_iter:
            yield chunk
            bytes_written += len(chunk)
    except Exception:
        msg = _("An error occurred reading from backend storage "
                "for image %(image_id)s") % locals()
        LOG.exception(msg)
        raise

    notify_cb(bytes_written)

    if expected_size != bytes_written:
        msg = _("Backend storage for image %(image_id)s "
                "disconnected after writing only %(bytes_written)d "
                "bytes") % locals()
        LOG.error(msg)
        raise exception.GlanceException(_("Corrupt image download for "
                                          "image %(image_id)s") % locals())


def image_send_notification(notifier, context, bytes_written, expected_size,
        image_meta, remote_address):
    """Send an image.send message to the notifier."""
    try:
        payload = {
            'bytes_sent': bytes_written,
            'image_id': image_meta['id'],
            'owner_id': image_meta['owner'],
            'receiver_tenant_id': context.tenant,
            'receiver_user_id': context.user,
            'destination_ip': remote_address,
        }
        if bytes_written != expected_size:
            notify = notifier.error
        else:
            notify = notifier.info

        notify('image.send', payload)

    except Exception:
        msg = _("An error occurred during image.send notification")
        LOG.exception(msg)
        raise


def get_image_send_notify_cb(context, image_meta, expected_size, notifier,
        remote_address):
    def notify(bytes_written):
        image_send_notification(notifier, context, bytes_written,
                expected_size, image_meta, remote_address)
    return notify



