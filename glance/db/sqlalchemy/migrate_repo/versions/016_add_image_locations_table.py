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

from glance.db.sqlalchemy.migrate_repo import schema


def get_image_locations_table(meta):
    #NOTE(bcwaldon): load the images table for the ForeignKey below
    sqlalchemy.Table('images', meta, autoload=True)

    return sqlalchemy.Table('image_locations', meta,
                            sqlalchemy.Column('id',
                                              schema.Integer(),
                                              primary_key=True,
                                              nullable=False),
                            sqlalchemy.Column('image_id',
                                              schema.String(36),
                                              sqlalchemy.ForeignKey('images.id'),
                                              nullable=False,
                                              index=True),
                            sqlalchemy.Column('value',
                                              schema.Text(),
                                              nullable=False),
                            sqlalchemy.Column('created_at',
                                              schema.DateTime(),
                                              nullable=False),
                            sqlalchemy.Column('updated_at',
                                              schema.DateTime()),
                            sqlalchemy.Column('deleted_at',
                                              schema.DateTime()),
                            sqlalchemy.Column('deleted',
                                              schema.Boolean(),
                                              nullable=False,
                                              default=False,
                                              index=True),
            )


def upgrade(migrate_engine):
    meta = sqlalchemy.schema.MetaData()
    meta.bind = migrate_engine

    image_locations_table = get_image_locations_table(meta)
    schema.create_tables([image_locations_table])


def downgrade(migrate_engine):
    meta = sqlalchemy.schema.MetaData()
    meta.bind = migrate_engine

    image_locations_table = get_image_locations_table(meta)
    schema.drop_tables([image_locations_table])