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

from sqlalchemy import schema
import sqlalchemy.exc

from glance.db.sqlalchemy.migrate_repo import schema as glance_schema
import glance.openstack.common.log as logging


LOG = logging.getLogger(__name__)

columns = [
    schema.Column('created_at', glance_schema.DateTime()),
    schema.Column('updated_at', glance_schema.DateTime()),
    schema.Column('deleted_at', glance_schema.DateTime()),
    schema.Column('deleted', glance_schema.Boolean()),
]


def upgrade(migrate_engine):
    meta = schema.MetaData()
    meta.bind = migrate_engine
    image_tags = schema.Table('image_tags', meta, autoload=True)
    for column in columns:
        try:
            image_tags.create_column(column)
        except sqlalchemy.exc.OperationalError:
            msg = _('Unable to create column \'%s\' - assuming it exists.')
            LOG.info(msg % column.name)


def downgrade(migrate_engine):
    meta = schema.MetaData()
    meta.bind = migrate_engine
    image_tags = schema.Table('image_tags', meta, autoload=True)
    for column in columns:
        image_tags.drop_column(column)
