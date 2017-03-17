#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Fetch a work from DSpace using direct access to Postgres DB
Upload a work to ORCID in XML format

Developed on Python 3.4
"""

from __future__ import print_function
from dspace import DSpace
from jinja2 import Environment, PackageLoader, select_autoescape
import requests
import configparser


# ORCID client app's ID (this program)
#CLIENT_APP = 'APP-LT1GI96T0HCIQY8N'  # sandbox member
CLIENT_APP = 'APP-WTHDFZPAUVXQW8GG'  # production member


def get_work_from_dspace(handle, xmlfile):
    """
    Given DSpace handle, fetches metadata of the work and stores it to xmlfile.
    Access DSpace using direct access to Postgres DB
    """
    dspace = DSpace(separator='_')
    metadata = dspace.get_metadata_in_document_lang(handle)

    env = Environment(
        trim_blocks=True,
        loader=PackageLoader('myapp', 'templates'),
        autoescape=select_autoescape(['xml'])
    )

    template = env.get_template('works.xml')
#    print(metadata)
#    print(template.render(metadata))
    xml = template.render(metadata)
    with open(xmlfile, 'wb') as outfile:
        outfile.write(xml.encode('utf-8'))


def upload(dspace, orcid, xmlfile):
    """Upload a work to ORCID in XML format"""

    token = dspace.lookup_token(CLIENT_APP, orcid, '/activities/update')
    baseurl = dspace.lookup_env(orcid)
    url = '%s/v2.0/%s/work' % (baseurl, orcid)
    headers = {
        'Content-type': 'application/vnd.orcid+xml',
        'Authorization': 'Bearer %s' % token,
    }

    with open(xmlfile, 'rb') as data:
        response = requests.post(url, headers=headers, data=data)
        if not response.ok:
            print(response.text)
        response.raise_for_status()


def upload_all(dspace, orcid, handles=[]):
    """Given a list of DSpace handles, upload all works to ORCID in XML format"""
    for handle in handles:
        get_work_from_dspace(handle, 'new.xml')
        print("Adding %s to ORCID..." % handle)
        try:
            upload(dspace, orcid, 'new.xml')
        except requests.exceptions.HTTPError as err:
            if err.response.status_code == 409:
                print("  Skipping (ORCID API reports a duplicate)")
            else:
                raise


def get_all_uploaded(dspace, orcid):
    """Given an ORCID ID, get the put codes of all works uploaded by this client app"""

    baseurl = dspace.lookup_env(orcid)
    if baseurl == 'https://api.sandbox.orcid.org':
        baseurl = 'https://pub.sandbox.orcid.org'
    else:
        baseurl = 'https://pub.orcid.org'

    url = '%s/v2.0/%s/works' % (baseurl, orcid)
    headers = {
        'Content-type': 'application/json',
    }

    response = requests.get(url, headers=headers)
    if not response.ok:
        print(response.text)
    response.raise_for_status()

    json = response.json()
    for i in json['group']:
        print("%s") % i


if __name__ == "__main__":
    orcid = '0000-0012-3456-789X'

    dspace = DSpace(separator='_')
    works = dspace.get_author_publications(orcid)
    print("%s : %i works from DSpace" % (orcid, len(works)))
    upload_all(dspace, orcid, works)  # upload a single author
