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

"""
While SQLAlchemy/sqlalchemy-migrate should abstract this correctly,
there are known issues with these libraries so SQLite and non-SQLite
migrations must be done separately.
"""
import anydbm
import shelve

import copy
import migrate
import sqlalchemy
from sqlalchemy import *

import glance.common.utils


class IdMapper(object):
    def __init__(self, shelf):
        self.shelf = shelf

    def get_uuid_for(self, int_id):
        print 'Get uuid for %s' % int_id
        key = self._int_key(int_id)
        if not key in self.shelf:
            uuid = glance.common.utils.generate_uuid()
            self._insert_record(int_id, uuid)
            return uuid
        return self.shelf[key]

    def get_int_id_for(self, uuid):
        print 'Get int id for %s' % uuid
        key = self._uuid_key(uuid)
        if not key in self.shelf:
            int_id = self._next_int_id
            self._insert_record(int_id, uuid)
            return int_id
        return self.shelf[key]

    def _int_key(self, int_id):
        return 'int:%d' % int_id

    def _uuid_key(self, uuid):
        return 'uuid:%s' % uuid.encode('ascii')

    def _insert_record(self, int_id, uuid):
        print 'MJW %s -> %s' % (int_id, uuid)
        if int_id >= self._next_int_id:
            self._next_int_id = int_id + 1
        int_key = self._int_key(int_id)
        uuid_key = self._uuid_key(uuid)
        self.shelf[int_key] = uuid
        self.shelf[uuid_key] = int_id

    @property
    def _next_int_id(self):
        if not 'next_int_id' in self.shelf:
            self.shelf['next_int_id'] = 1
        print 'GET next_int_id (= %s)' % self.shelf['next_int_id']
        return self.shelf['next_int_id']

    @_next_int_id.setter
    def _next_int_id(self, value):
        print 'SET next_int_id to %s' % value
        self.shelf['next_int_id'] = value


def upgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    t_images = _get_table('images', meta)
    t_image_members = _get_table('image_members', meta)
    t_image_properties = _get_table('image_properties', meta)

    _add_uuid_columns(t_images, t_image_members, t_image_properties)
    _populate_uuids(t_images, t_image_members, t_image_properties)
    _rename_old_tables(t_images, t_image_members, t_image_properties)

    if migrate_engine.url.get_dialect().name in ["sqlite", "postgresql"]:
        _drop_indexes(migrate_engine)

    # Get a new metadata instance to get around the stale reflection cache
    meta = MetaData()
    meta.bind = migrate_engine
    _create_uuid_tables(meta)

    _load_data_into_uuid_tables(migrate_engine)

    _get_table('image_members_premigrate', meta).drop()
    _get_table('image_properties_premigrate', meta).drop()
    _get_table('images_premigrate', meta).drop()


def _get_table(table_name, metadata):
    """Return a sqlalchemy Table definition with associated metadata."""
    return Table(table_name, metadata, autoload=True)


def _add_uuid_columns(*tables):
    for table in tables:
        uuid_column = Column('image_uuid', String(36))
        uuid_column.create(table)


def _populate_uuids(t_images, t_image_members, t_image_properties):
    shelf = shelve.open('uuid_migration')
    id_mapper = IdMapper(shelf)

    images = list(t_images.select().execute())

    for image in images:
        image_id = image['id']
        image_uuid = id_mapper.get_uuid_for(image_id)

        t_images.update().\
            where(t_images.c.id == image_id).\
            values(image_uuid=image_uuid).execute()

        t_image_members.update().\
            where(t_image_members.c.image_id == image_id).\
            values(image_uuid=image_uuid).execute()

        t_image_properties.update().\
            where(t_image_properties.c.image_id == image_id).\
            values(image_uuid=image_uuid).execute()

        t_image_properties.update().\
            where(and_(or_(t_image_properties.c.name == 'kernel_id',
                           t_image_properties.c.name == 'ramdisk_id'),
                       t_image_properties.c.value == str(image_id))).\
            values(value=image_uuid).execute()


def _rename_old_tables(t_images, t_image_members, t_image_properties):
    t_images.rename('images_premigrate')
    t_image_members.rename('image_members_premigrate')
    t_image_properties.rename('image_properties_premigrate')


def _drop_indexes(engine):
    """In some databases (notably not MySQL) indices exist independently from
    tables, and so two indices on different tables are not allowed to have the
    same name. For this reason, we must delete indices on the tables we
    recently renamed and want to recreate."""
    indexes = [
        'ix_images_is_public',
        'ix_images_deleted',
        'ix_image_members_image_id',
        'ix_image_members_image_id_member',
        'ix_image_members_deleted',
        'ix_image_properties_deleted',
        'ix_image_properties_image_id',
        'ix_image_properties_image_id_name',
    ]

    for index in indexes:
        # NOTE(markwash): specify IF EXISTS because of bug 1051123
        engine.execute('DROP INDEX IF EXISTS %s' % index)


def _create_uuid_tables(meta):
    t_images = Table('images', meta,
        Column('id', String(36), primary_key=True, nullable=False),
        Column('name', String(255)),
        Column('size', BigInteger()),
        Column('status', String(30), nullable=False),
        Column('is_public', Boolean(), nullable=False, default=False,
               index=True),
        Column('location', Text()),
        Column('created_at', DateTime(), nullable=False),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()),
        Column('deleted', Boolean(), nullable=False, default=False,
               index=True),
        Column('disk_format', String(20)),
        Column('container_format', String(20)),
        Column('checksum', String(32)),
        Column('owner', String(255)),
        Column('min_disk', Integer(), nullable=False),
        Column('min_ram', Integer(), nullable=False),
        mysql_engine='InnoDB',
    )

    t_images.create()

    t_image_members = Table('image_members', meta,
        Column('id', Integer(), primary_key=True, nullable=False),
        Column('image_id', String(36), ForeignKey('images.id'), nullable=False,
               index=True),
        Column('member', String(255), nullable=False),
        Column('can_share', Boolean(), nullable=False, default=False),
        Column('created_at', DateTime(), nullable=False),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()),
        Column('deleted', Boolean(), nullable=False, default=False,
               index=True),
        UniqueConstraint('image_id', 'member'),
        mysql_engine='InnoDB',
    )

    Index('ix_image_members_image_id_member', t_image_members.c.image_id,
          t_image_members.c.member)

    t_image_members.create()

    t_image_properties = Table('image_properties', meta,
        Column('id', Integer(), primary_key=True, nullable=False),
        Column('image_id', String(36), ForeignKey('images.id'), nullable=False,
               index=True),
        Column('name', String(255), nullable=False),
        Column('value', Text()),
        Column('created_at', DateTime(), nullable=False),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()),
        Column('deleted', Boolean(), nullable=False, default=False,
               index=True),
        UniqueConstraint('image_id', 'name'),
        mysql_engine='InnoDB',
    )

    Index('ix_image_properties_image_id_name', t_image_properties.c.image_id,
          t_image_properties.c.name)

    t_image_properties.create()


def _load_data_into_uuid_tables(engine):
    sql_commands = [
        """INSERT INTO images
               (id, name, size, status, is_public, location, created_at,
                updated_at, deleted_at, deleted, disk_format,
                container_format, checksum, owner, min_disk, min_ram)
           SELECT
               image_uuid, name, size, status, is_public, location, created_at,
               updated_at, deleted_at, deleted, disk_format,
               container_format, checksum, owner, min_disk, min_ram
           FROM images_premigrate;
        """,
        """INSERT INTO image_members
               (id, image_id, member, can_share, created_at, updated_at,
                deleted_at, deleted)
           SELECT
               id, image_uuid, member, can_share, created_at, updated_at,
               deleted_at, deleted
           FROM image_members_premigrate;
        """,
        """INSERT INTO image_properties
               (id, image_id, name, value, created_at, updated_at,
                deleted_at, deleted)
           SELECT
               id, image_uuid, name, value, created_at, updated_at,
               deleted_at, deleted
           FROM image_properties_premigrate;
        """,
    ]

<<<<<<< HEAD
def _get_foreign_keys(t_images, t_image_members, t_image_properties):
    """Retrieve and return foreign keys for members/properties tables."""
    image_members_fk_name = list(t_image_members.foreign_keys)[0].name
    image_properties_fk_name = list(t_image_properties.foreign_keys)[0].name

    fk1 = migrate.ForeignKeyConstraint([t_image_members.c.image_id],
                                       [t_images.c.id],
                                       name=image_members_fk_name)

    fk2 = migrate.ForeignKeyConstraint([t_image_properties.c.image_id],
                                       [t_images.c.id],
                                       name=image_properties_fk_name)

    return fk1, fk2
=======
    for command in sql_commands:
        engine.execute(command)


def downgrade(migrate_engine):
    meta = MetaData()
    meta.bind = migrate_engine

    t_images = _get_table('images', meta)
    t_image_members = _get_table('image_members', meta)
    t_image_properties = _get_table('image_properties', meta)

    _add_intid_columns(t_images, t_image_members, t_image_properties)
    _populate_intids(t_images, t_image_members, t_image_properties)
    _rename_old_tables(t_images, t_image_members, t_image_properties)
>>>>>>> a26e574... Improve integer id -> string uuid migration

    if migrate_engine.url.get_dialect().name in ["sqlite", "postgresql"]:
        _drop_indexes(migrate_engine)

    # Get a new metadata instance to get around the stale reflection cache
    meta = MetaData()
    meta.bind = migrate_engine
    _create_intid_tables(meta)

    _load_data_into_intid_tables(migrate_engine)

    _get_table('image_members_premigrate', meta).drop()
    _get_table('image_properties_premigrate', meta).drop()
    _get_table('images_premigrate', meta).drop()


def _add_intid_columns(*tables):
    for table in tables:
        uuid_column = Column('image_intid', Integer())
        uuid_column.create(table)


def _populate_intids(t_images, t_image_members, t_image_properties):
    try:
        shelf = shelve.open('uuid_migration', flag='w')
    except anydbm.error:
        # If no previously created uuid migration file exists, don't bother
        # with creating one now. Instead use a harmless dictionary.
        shelf = {}
    id_mapper = IdMapper(shelf)

    images = list(t_images.select().execute())

    for image in images:
        image_id = image['id']
        image_intid = id_mapper.get_int_id_for(image_id)

        t_images.update().\
            where(t_images.c.id == image_id).\
            values(image_intid=image_intid).execute()

        t_image_members.update().\
            where(t_image_members.c.image_id == image_id).\
            values(image_intid=image_intid).execute()

        t_image_properties.update().\
            where(t_image_properties.c.image_id == image_id).\
            values(image_intid=image_intid).execute()

        t_image_properties.update().\
            where(and_(or_(t_image_properties.c.name == 'kernel_id',
                           t_image_properties.c.name == 'ramdisk_id'),
                       t_image_properties.c.value == image_id)).\
            values(value=image_intid).execute()


def _create_intid_tables(meta):
    t_images = Table('images', meta,
        Column('id', Integer(), primary_key=True, nullable=False),
        Column('name', String(255)),
        Column('size', BigInteger()),
        Column('status', String(30), nullable=False),
        Column('is_public', Boolean(), nullable=False, default=False,
               index=True),
        Column('location', Text()),
        Column('created_at', DateTime(), nullable=False),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()),
        Column('deleted', Boolean(), nullable=False, default=False,
               index=True),
        Column('disk_format', String(20)),
        Column('container_format', String(20)),
        Column('checksum', String(32)),
        Column('owner', String(255)),
        Column('min_disk', Integer(), nullable=False),
        Column('min_ram', Integer(), nullable=False),
        mysql_engine='InnoDB',
    )

    t_images.create()

    t_image_members = Table('image_members', meta,
        Column('id', Integer(), primary_key=True, nullable=False),
        Column('image_id', Integer(), ForeignKey('images.id'), nullable=False,
               index=True),
        Column('member', String(255), nullable=False),
        Column('can_share', Boolean(), nullable=False, default=False),
        Column('created_at', DateTime(), nullable=False),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()),
        Column('deleted', Boolean(), nullable=False, default=False,
               index=True),
        UniqueConstraint('image_id', 'member'),
        mysql_engine='InnoDB',
    )

    Index('ix_image_members_image_id_member', t_image_members.c.image_id,
          t_image_members.c.member)

    t_image_members.create()

    t_image_properties = Table('image_properties', meta,
        Column('id', Integer(), primary_key=True, nullable=False),
        Column('image_id', Integer(), ForeignKey('images.id'), nullable=False,
               index=True),
        Column('name', String(255), nullable=False),
        Column('value', Text()),
        Column('created_at', DateTime(), nullable=False),
        Column('updated_at', DateTime()),
        Column('deleted_at', DateTime()),
        Column('deleted', Boolean(), nullable=False, default=False,
               index=True),
        UniqueConstraint('image_id', 'name'),
        mysql_engine='InnoDB',
    )

    Index('ix_image_properties_image_id_name', t_image_properties.c.image_id,
          t_image_properties.c.name)

    t_image_properties.create()


def _load_data_into_intid_tables(engine):
    sql_commands = [
        """INSERT INTO images
                (id, name, size, status, is_public, location, created_at,
                 updated_at, deleted_at, deleted, disk_format,
                 container_format, checksum, owner, min_disk, min_ram)
            SELECT
                image_intid, name, size, status, is_public, location,
                created_at, updated_at, deleted_at, deleted, disk_format,
                container_format, checksum, owner, min_disk, min_ram
            FROM images_premigrate;
        """,
        """INSERT INTO image_members
                (id, image_id, member, can_share, created_at, updated_at,
                 deleted_at, deleted)
            SELECT
                id, image_intid, member, can_share, created_at, updated_at,
                deleted_at, deleted
            FROM image_members_premigrate;
        """,
        """INSERT INTO image_properties
                (id, image_id, name, value, created_at, updated_at,
                 deleted_at, deleted)
            SELECT
                id, image_intid, name, value, created_at, updated_at,
                deleted_at, deleted
            FROM image_properties_premigrate;
        """,
    ]

    for command in sql_commands:
        engine.execute(command)
