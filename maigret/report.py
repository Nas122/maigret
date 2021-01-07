import csv
from datetime import datetime
import logging
import os
import xmind

from jinja2 import Template
import pycountry

from .result import QueryStatus
from .utils import is_country_tag, CaseConverter, enrich_link_str


def save_csv_report(username: str, results: dict):
    with open(username + '.csv', 'w', newline='', encoding='utf-8') as csvfile:
        save_csv_report_to_file(username, results, csvfile)


def save_html_report(username_results: list):
    brief_text = []
    usernames = {}
    extended_info_count = 0
    tags = {}
    supposed_data = {}
    allowed_fields = ['fullname', 'gender']
    first_seen = None
    first_seen_format = '%Y-%m-%d %H:%M:%S'

    for username, id_type, results in username_results:
        found_accounts = 0
        new_ids = []
        usernames[username] = {'type': id_type}

        for website_name in results:
            dictionary = results[website_name]
            # TODO: fix no site data issue
            if not dictionary:
                continue

            status = dictionary.get('status')
            if status.ids_data:
                dictionary['ids_data'] = status.ids_data
                extended_info_count += 1

                # detect first seen
                created_at = status.ids_data.get('created_at')
                if created_at:
                    if first_seen is None:
                        first_seen = created_at
                    else:
                        known_time = datetime.strptime(first_seen, first_seen_format)
                        new_time = datetime.strptime(created_at, first_seen_format)
                        if new_time < known_time:
                            first_seen = created_at

                for k, v in status.ids_data.items():
                    # suppose target data
                    field = 'fullname' if k == 'name' else k
                    if not field in supposed_data:
                        supposed_data[field] = []
                    supposed_data[field].append(v)
                    # suppose country
                    if k in ['country', 'locale']:
                        try:
                            if is_country_tag(k):
                                tag = pycountry.countries.get(alpha_2=v).alpha_2.lower()
                            else:
                                tag = pycountry.countries.search_fuzzy(v)[0].alpha_2.lower()
                            # TODO: move countries to another struct
                            tags[tag] = tags.get(tag, 0) + 1
                        except Exception as e:
                            logging.debug('pycountry exception', exc_info=True)

            new_usernames = dictionary.get('ids_usernames')
            if new_usernames:
                for u, utype in new_usernames.items():
                    if not u in usernames:
                        new_ids.append((u, utype))
                        usernames[u] = {'type': utype}

            if status.status == QueryStatus.CLAIMED:
                found_accounts += 1
                dictionary['found'] = True
            else:
                continue

            if not dictionary.get('is_similar'):
                # ignore non-exact search results
                if status.tags:
                    for t in status.tags:
                        tags[t] = tags.get(t, 0) + 1


        brief_text.append(f'Search by {id_type} {username} returned {found_accounts} accounts.')

        if new_ids:
            ids_list = []
            for u, t in new_ids:
                ids_list.append(f'{u} ({t})' if t != 'username' else u)
            brief_text.append(f'Found target\'s other IDs: ' + ', '.join(ids_list) + '.')

    brief_text.append(f'Extended info extracted from {extended_info_count} accounts.')

    # template generation
    template_text = open(os.path.join(os.path.dirname(os.path.realpath(__file__)),
                         "resources/simple_report.tpl")).read()
    template = Template(template_text)

    template.globals['title'] = CaseConverter.snake_to_title
    template.globals['detect_link'] = enrich_link_str

    brief = ' '.join(brief_text).strip()
    tuple_sort = lambda d: sorted(d, key=lambda x: x[1], reverse=True)

    if 'global' in tags:
        # remove tag 'global' useless for country detection
        del tags['global']

    first_username = username_results[0][0]
    countries_lists = list(filter(lambda x: is_country_tag(x[0]), tags.items()))
    interests_list = list(filter(lambda x: not is_country_tag(x[0]), tags.items()))

    filtered_supposed_data = {CaseConverter.snake_to_title(k): v[0]
                              for k, v in supposed_data.items()
                              if k in allowed_fields}

    filled_template = template.render(username=first_username,
                                      brief=brief,
                                      results=username_results,
                                      first_seen=first_seen,
                                      interests_tuple_list=tuple_sort(interests_list),
                                      countries_tuple_list=tuple_sort(countries_lists),
                                      supposed_data=filtered_supposed_data,
                                      generated_at=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                      )
    # save report
    html_filename = f'report_{first_username}.html'
    with open(html_filename, 'w') as f:
        f.write(filled_template)

def save_csv_report_to_file(username: str, results: dict, csvfile):
    print(results)
    writer = csv.writer(csvfile)
    writer.writerow(['username',
                     'name',
                     'url_main',
                     'url_user',
                     'exists',
                     'http_status'
                     ]
                    )
    for site in results:
        writer.writerow([username,
                         site,
                         results[site]['url_main'],
                         results[site]['url_user'],
                         str(results[site]['status'].status),
                         results[site]['http_status'],
                        ])


def genxmindfile(filename, username, results):
    print(f'Generating XMIND8 file for username {username}')
    if os.path.exists(filename):
        os.remove(filename)
    workbook = xmind.load(filename)
    sheet = workbook.getPrimarySheet()
    design_sheet1(sheet, username, results)
    xmind.save(workbook, path=filename)


def design_sheet1(sheet, username, results):
    ##all tag list
    alltags = {}

    sheet.setTitle("%s Analysis"%(username))
    root_topic1 = sheet.getRootTopic()
    root_topic1.setTitle("%s"%(username))

    undefinedsection = root_topic1.addSubTopic()
    undefinedsection.setTitle("Undefined")
    alltags["undefined"] = undefinedsection

    for website_name in results:
        dictionary = results[website_name]

        if dictionary.get("status").status == QueryStatus.CLAIMED:
            ## firsttime I found that entry
            for tag in dictionary.get("status").tags:
                if tag.strip() == "":
                    continue
                if tag not in alltags.keys():
                    if not is_country_tag(tag):
                        tagsection = root_topic1.addSubTopic()
                        tagsection.setTitle(tag)
                        alltags[tag] = tagsection

            category = None
            userlink=  None
            for tag in dictionary.get("status").tags:
                if tag.strip() == "":
                    continue
                if not is_country_tag(tag):
                    category = tag

            if category is None:
                category = "undefined"
                userlink = undefinedsection.addSubTopic()
            else:
                userlink = alltags[category].addSubTopic()
            userlink.addLabel(dictionary.get("status").site_url_user)

            #for tag in dictionary.get("status").tags:
            #    if( tag != category ):
            #       sheet.createRelationship(userlink.getID(), alltags[tag].getID(),"other tag")
