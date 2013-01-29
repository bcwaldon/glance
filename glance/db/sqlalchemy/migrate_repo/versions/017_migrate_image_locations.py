# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2011 OpenStack LLC.
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

import sqlalchemy

import logging as base_logging
import glance.openstack.common.log as logging


LOG = logging.getLogger(__name__)

sa_logger = base_logging.getLogger('sqlalchemy.engine')
sa_logger.setLevel(base_logging.DEBUG)


def get_images_table(meta):
    return sqlalchemy.Table('images', meta, autoload=True)


def get_image_locations_table(meta):
    return sqlalchemy.Table('image_locations', meta, autoload=True)


def upgrade(migrate_engine):
    meta = sqlalchemy.schema.MetaData()
    meta.bind = migrate_engine

    images_table = get_images_table(meta)
    image_locations_table = get_image_locations_table(meta)

    for image in images_table.select().execute():
        if image.location is not None:
            image_locations_table.insert(values={'image_id': image.id, 'value': image.location}).execute()


def downgrade(migrate_engine):
    meta = sqlalchemy.schema.MetaData()
    meta.bind = migrate_engine

    images_table = get_images_table(meta)
    image_locations_table = get_image_locations_table(meta)

    for image_location in image_locations_table.select().execute():
        images_table.update(values={'location': image_location.value}).where(id=image_location.image_id).execute()
