#!/usr/bin/env python
# -*- coding: utf-8 -*-

_about = '''
App Changelog retrieves information from the iTunes App Store and generates a CSV report
containing interesting information on each App listed in the input CSV file.

Input: A CSV file with the following columns:

    Row Number
    Company Name
    iTunes App Store URL

We include Row Number as we are often using a subset of a larger list of companies, so the
supplied Row Number allows for easier mapping between the original input and final output.

Output: A CSV file with the following columns:

    Row Number
    Company Name
    iTunes App Store URL
    Number of Ratings
    Average Rating
    App Age
    ╔ Version #    ╗
    ╚ Version Date ╝

    The above two columns repeat for each version of the app within the interesting time range.

'''

from bs4 import BeautifulSoup

import argparse
import csv
import datetime
import json
import os
import sys
import urllib2

in_csv = 'input.csv'
out_csv = 'output.csv'
err_csv = 'errors.csv'


def parse(number, company, url, verbose):

    raw_data = {}

    try:
        # craft the request
        request = urllib2.Request(url.replace('https', 'http'))
        request.add_header('User-Agent', 'iTunes/12.1.2 (Macintosh; OS X 10.10.3) AppleWebKit/0600.5.17')

        # make the request and read the response body
        response = urllib2.urlopen(request).read()
        body = BeautifulSoup(response)

        # pull out the response JSON data
        scripts = body.findAll('script')
        server_data = scripts[2].text.split('its.serverData=')[1]
        raw_data = json.loads(server_data)
    except Exception as e:
        if verbose:
            print 'Error retrieving JSON data: %s, %s, %s' % (number, company, e)
        return False

    data = {}

    try:
        app_data = raw_data.get('pageData').get('softwarePageData')
        changelog = app_data.get('versionHistory')
        app_id = app_data.get('id')

        rating_data = raw_data.get('storePlatformData').get('product-dv-product').get('results').get(app_id).get('userRating')
        rating = rating_data.get('value')
        rating_count = rating_data.get('ratingCount')

        if not changelog:
            raise ValueError('No changelog data found.')
            return False

        versions = []
        oldest = 0

        for change in changelog:
            version = change.get('versionString')
            release = change.get('releaseDate')

            releasedate = datetime.datetime.strptime(release, "%Y-%m-%dT%H:%M:%SZ").date()
            now = datetime.datetime.now().date()

            diff = (now - releasedate).days

            if diff > oldest:
                oldest = diff

            # we don't care about changes past 2 years from today
            if diff > (365*2):
                continue

            versions.append((version, releasedate.isoformat()))

        data = {
            'number': number,
            'company': company,
            'url': url,
            'num_ratings': rating_count,
            'rating': rating,
            'age': oldest,
            'versions': versions
        }

    except Exception as e:
        if verbose:
            print 'Error parsing JSON data: %s, %s, %s' % (number, company, e)
        return False

    return data


def main(in_file, out_file, err_file, verbose=False):
    with open(in_file, 'rb') as csvfile:
        reader = csv.reader(csvfile, delimiter=',', quotechar='|')

        for row in reader:
            try:
                number, company, url = row
            except Exception as e:
                if verbose:
                    print e
                continue

            company = company.decode('utf-8')
            url = url.decode('utf-8')

            if verbose:
                print 'Parsing %s' % row[0]

            result = parse(number, company, url, verbose)

            # if the response is empty but there were no errors raised
            if result == {}:
                if verbose:
                    print 'No result for row %s' % row[0]
            # fall through to any type of error
            elif not result:
                # record error for future rerun
                with open(err_file, 'a') as err:
                    err.write('%s\n' % ','.join(row))
                continue

            if verbose:
                print json.dumps(result, indent=4, separators=(',', ': '))

            with open(out_file, 'a') as out:
                output = '%s,%s,%s,%s,%s,%s,%s\n' % (
                    result['number'],
                    result['company'],
                    result['url'],
                    result['num_ratings'],
                    result['rating'],
                    result['age'],
                    ','.join(['%s,%s' % (x[0], x[1]) for x in result['versions']])
                )
                out.write(output.encode('utf-8'))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description=_about,
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('-i','--input', help='Input CSV')
    parser.add_argument('-o','--output', help='Output CSV')
    parser.add_argument('-l','--log', help='Logging CSV')
    parser.add_argument('-x','--overwrite', help='Overwrite', action='store_true')
    parser.add_argument('-v','--verbose', help='Verbose mode', action='store_true')
    args = parser.parse_args()

    in_csv = args.input or in_csv
    out_csv = args.output or out_csv
    err_csv = args.log or err_csv

    if not os.path.isfile(in_csv):
        parser.error('Input file does not exist.')

    if os.path.isfile(out_csv) and not args.overwrite:
        parser.error('Output file exists and overwrite is not set.')

    # clean out the output CSV
    open(out_csv, 'w')

    main(in_csv, out_csv, err_csv, args.verbose)
