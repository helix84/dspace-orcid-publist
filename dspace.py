#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Access to DSpace using direct access to Postgres DB

Developed on Python 3.4
"""

from __future__ import print_function
import psycopg2 as psql_dbapi2
import configparser


class BidirectionalDict(dict):
    """A dictionary where you can look up by both key and value."""
    def __setitem__(self, key, val):
        dict.__setitem__(self, key, val)
        dict.__setitem__(self, val, key)

    def __delitem__(self, key):
        dict.__delitem__(self, self[key])
        dict.__delitem__(self, key)


class DSpace(object):
    """Access to DSpace using DB connection (Postgres)"""
    def __init__(self, separator='.'):
        """Initialize DB connection"""
        config = configparser.RawConfigParser()
        config.read('config/config.ini')
        dspace_conn_str = config.get('database', 'dspacedb')

        self.con = psql_dbapi2.connect(dspace_conn_str)
        self.cur = self.con.cursor()

        self.separator = separator
        self.fields = self.get_metadata_fields(separator)

    def __del__(self):
        """Close DB connection"""
        self.cur.close()
        self.con.close()

    def get_metadata_field_id(self, schema, element, qualifier=None):
        """Get DB ID of the dc.identifier.stag field"""
        self.cur.execute(
            """SELECT metadata_schema_id FROM metadataschemaregistry
            WHERE short_id = %(schema)s""",
            {'schema': schema}
        )
        schema_id = self.cur.fetchone()[0]

        if qualifier is None:
            self.cur.execute(
                """SELECT metadata_field_id FROM metadatafieldregistry
                WHERE metadata_schema_id=%(s_id)s AND element=%(element)s
                AND qualifier IS NULL """,
                {'s_id': schema_id, 'element': element}
            )
            print('DEBUG: qualifier is None')
        else:
            self.cur.execute(
                """SELECT metadata_field_id FROM metadatafieldregistry
                WHERE metadata_schema_id=%(s_id)s AND element=%(element)s
                AND qualifier=%(qualifier)s """,
                {'s_id': schema_id, 'element': element, 'qualifier': qualifier}
            )

        result = self.cur.fetchone()
        if result is not None:
            return result[0]
        else:
            return None

    def get_metadata_fields(self, separator='.'):
        """Get DB ID of the dc.identifier.stag field"""
        self.cur.execute(
            """SELECT metadata_field_id, short_id AS schema, element, qualifier
            FROM metadatafieldregistry mfr
            JOIN metadataschemaregistry msr
            ON msr.metadata_schema_id = mfr.metadata_schema_id;
            """
        )
        fields = BidirectionalDict()
        for record in self.cur:
            if record[3] is not None:
                fieldname = separator.join([record[1], record[2], record[3]])
            else:
                fieldname = separator.join([record[1], record[2]])
            fields[record[0]] = fieldname
        return fields

    def get_itemid(self, handle):
        """Get item ID from a given item handle"""
        self.cur.execute(
            """SELECT resource_id
            FROM handle
            WHERE handle.resource_type_id = 2
            AND handle = %(handle)s """,
            {'handle': handle}
        )
        return int(self.cur.fetchone()[0])

    def get_handle(self, resource_id, resource_type_id=2):
        """Get handle from a given item ID"""
        self.cur.execute(
            """SELECT handle
               FROM handle
               WHERE handle.resource_type_id = %(resource_type_id)s
               AND handle.resource_id = %(resource_id)s """,
            {'resource_type_id': resource_type_id, 'resource_id': resource_id}
        )
        return self.cur.fetchone()[0]

    def get_metadata(self, item_id):
        """Get a list of all metadata of the given item"""
        if isinstance(item_id, str):
            # if given a string, assume it's a handle and look up item ID
            item_id = self.get_itemid(item_id)
        self.cur.execute(
            """SELECT metadata_field_id, text_value, text_lang
            FROM metadatavalue
            WHERE resource_type_id = 2
            AND resource_id=%(item_id)s """,
            {'item_id': item_id}
        )
        metadata = {}
        for record in self.cur.fetchall():
            field = self.fields[record[0]]
            try:
                metadata[field].append(record[1])
            except KeyError:
                metadata[field] = [record[1]]
        return metadata

    def get_metadata_with_lang(self, item_id):
        """
        Get a list of all metadata of the given item,
        including language for each metadata value
        """
        if isinstance(item_id, str):
            # if given a string, assume it's a handle and look up item ID
            item_id = self.get_itemid(item_id)
        self.cur.execute(
            """SELECT metadata_field_id, text_value, text_lang
            FROM metadatavalue
            WHERE resource_type_id = 2
            AND resource_id=%(item_id)s """,
            {'item_id': item_id}
        )
        metadata = {}
        for record in self.cur.fetchall():
            field = self.fields[record[0]]
            value = record[1]
            lang = record[2]
            if lang == '':
                lang = None
            if field in metadata:
                if lang in metadata[field]:
                    metadata[field][lang].append(value)
                else:
                    metadata[field][lang] = [value]
            else:
                metadata[field] = {}
                metadata[field][lang] = [value]
        return metadata

    def get_metadata_in_document_lang(self, item_id):
        """Get a list of all metadata of the given item, but keep only a single
        title"""
        metadata = self.get_metadata_with_lang(item_id)

        try:
            doc_lang = metadata['dc_language_iso'][0]
        except KeyError:
            langs = list(metadata['dc_title'].keys())
            doc_lang = langs[0]

        metadata_single_lang = {}
        for field in metadata:
            if doc_lang in metadata[field]:
                lang = doc_lang
            else:
                if None in metadata[field]:
                    lang = None
                else:
                    continue

            metadata_single_lang[field] = metadata[field][lang]

        return metadata_single_lang

    def get_author_names(self, orcid):
        """
        Get Author names from DSpace for a given ORCID.
        (local customization; not part of DSpace schema)
        """
        self.cur.execute(
            """SELECT "displayName"
            FROM utb_authors
            WHERE "ORCID"=%(orcid)s """,
            {'orcid': orcid}
        )
        if self.cur.rowcount == 1:
            return self.cur.fetchone()[0].split('||')
        else:
            return None

    def get_author_publications(self, orcid):
        """
        Get Author publication from DSpace for a given ORCID
        (even for multiple variants of their name).
        (local customization; not part of DSpace schema)
        """
        metadata_field_id = self.fields[
            'dc.contributor.author'.replace('.', self.separator)
        ]
        names = self.get_author_names(orcid)
        if names is None:
            return None

        handles = []
        for name in names:
            self.cur.execute(
                """SELECT handle
                FROM metadatavalue mv
                JOIN handle h ON h.resource_id = mv.resource_id
                WHERE mv.resource_type_id = 2
                AND metadata_field_id = %(metadata_field_id)s
                AND text_value = %(name)s
                ORDER BY 1 """,
                {
                    'metadata_field_id': metadata_field_id,
                    'name': name,
                }
            )
            if self.cur.rowcount <= 0:
                continue
            handles += [x[0] for x in self.cur.fetchall()]
        return handles

    def lookup_token(self, client_id, orcid, scope):
        """
        Get stored token for given client app ID and ORCID ID.
        (local customization; not part of DSpace schema)
        """
        self.cur.execute(
            """SELECT token
            FROM utb_orcid_tokens
            WHERE client_id=%(client_id)s
            AND orcid=%(orcid)s
            AND scope=%(scope)s """,
            {
                'client_id': client_id,
                'orcid': orcid,
                'scope': scope,
            }
        )
        if self.cur.rowcount >= 1:
            return self.cur.fetchone()[0]
        else:
            return None

    def lookup_env(self, orcid):
        """
        Get environment (sandbox/production) for given ORCID ID
        from the table of stored tokens.
        Return appropriate ORCID API base URL.
        (local customization; not part of DSpace schema)
        """
        self.cur.execute(
            """SELECT env
            FROM utb_orcid_tokens
            WHERE orcid=%(orcid)s """,
            {
                'orcid': orcid,
            }
        )
        if self.cur.rowcount >= 1:
            env = self.cur.fetchone()[0]
            if env == 'production':
                return 'https://api.orcid.org'
            else:
                return 'https://api.sandbox.orcid.org'
        else:
            return None


if __name__ == "__main__":
    dspace = DSpace()
#    md = dspace.get_metadata('123456789/123')
#    print(md)

#    print(dspace.get_author_names('XXX'))  # 0 results -> None
#    print(dspace.get_author_names('0000-0012-3456-789X'))  # 1 result -> ['']
#    print(dspace.get_author_names('0000-0001-1234-5678'))  # 2 results -> ['', '']

#    print(dspace.get_author_publications('0000-0001-1234-5678'))

#    md = dspace.get_metadata('123456789/123')
#    md = dspace.get_metadata_with_lang('123456789/123')
#    md = dspace.get_metadata_in_document_lang('123456789/123')
#    import pprint
#    pp = pprint.PrettyPrinter(depth=4)
#    pp.pprint(md)

#    print(dspace.lookup_token('APP-A1B2C3D4E5F6G7H8', '0000-0012-3456-789X', '/activities/update'))
