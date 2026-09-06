#!/usr/bin/env python3
import re
import sys
# from collections import defaultdict


def parse_foreca_list(content):
    lines = content.splitlines()
    continents = {}
    current_continent = None
    # current_country = None

    # Pattern for city line: ID/City-Country
    city_pattern = re.compile(r'^(\d+)/(.+)-([A-Za-z\s\-\'\(\)]+)$')

    # Map to normalize continent names
    continent_map = {
        'europe': 'Europe',
        'africa': 'Africa',
        'americas': 'Americas',
        'asia': 'Asia',
        'australia': 'Australia/Oceania',
        'oceania': 'Australia/Oceania'
    }

    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue

        # Detect continent (example: "#      E u r o p e      #")
        if line.startswith('#') and ('europe' in line.lower() or 'africa' in line.lower() or
                                     'americas' in line.lower() or 'asia' in line.lower() or
                                     'australia' in line.lower() or 'oceania' in line.lower()):
            for key, value in continent_map.items():
                if key in line.lower():
                    current_continent = value
                    if current_continent not in continents:
                        continents[current_continent] = {}
                        continents[current_continent]['_fixits'] = []
                    break
            i += 1
            continue

        # Country separator (########)
        if line.startswith('########'):
            # current_country = None
            i += 1
            continue

        # FIX IT comments
        if line.startswith('#') and 'FIX IT' in line:
            if current_continent:
                # Try to determine which country it belongs to
                # Example: "# FIX IT: SEND THE RIGHT ONE ON FORUM:
                # Belgium/Heist-op-den-Berg"
                match = re.search(r':\s*([A-Za-z\s\-]+)/', line)
                if match and current_continent:
                    country = match.group(1).strip()
                    # Ensure the country exists in the continent (it may be
                    # added later)
                    if country not in continents[current_continent]:
                        continents[current_continent][country] = {
                            'cities': [], 'fixits': []}
                    continents[current_continent][country]['fixits'].append(
                        line)
                else:
                    # Fixit without country -> attach to continent
                    continents[current_continent]['_fixits'].append(line)
            i += 1
            continue

        # Ignore other comments (example: "##  Albania")
        if line.startswith('#'):
            i += 1
            continue

        # City line
        match = city_pattern.match(line)
        if match:
            city_id, city_name, country = match.groups()
            if current_continent:
                if country not in continents[current_continent]:
                    continents[current_continent][country] = {
                        'cities': [], 'fixits': []}
                continents[current_continent][country]['cities'].append(
                    (city_id, city_name, line))
            i += 1
            continue

        # If nothing matches, print warning (optional)
        # print(f"Ignored line: {line[:50]}...")
        i += 1

    return continents


def sort_and_output(continents):
    out_lines = []
    # Fixed continent order (alphabetical but with Australia/Oceania at the
    # end)
    continent_order = [
        'Africa',
        'Americas',
        'Asia',
        'Australia/Oceania',
        'Europe']
    for continent in continent_order:
        if continent not in continents:
            continue
        data = continents[continent]
        # Continent header (with spaces like the original)
        header = {
            'Africa': '#      A f r i c a      #',
            'Americas': '#      A m e r i c a s      #',
            'Asia': '#      A s i a      #',
            'Australia/Oceania': '#      A u s t r a l i a / O c e a n i a      #',
            'Europe': '#      E u r o p e      #'}[continent]
        out_lines.append('')
        out_lines.append('#########################')
        out_lines.append(header)
        out_lines.append('#########################')
        out_lines.append('')

        # Countries in alphabetical order (ignoring special key '_fixits')
        countries = [c for c in data if not c.startswith('_')]
        for country in sorted(countries):
            country_data = data[country]
            cities = sorted(country_data['cities'], key=lambda x: x[1].lower())
            out_lines.append('########')
            out_lines.append(f'##  {country}')
            for _, _, city_line in cities:
                out_lines.append(city_line)
            # Add FIX IT specific to the country
            for fix in sorted(country_data.get('fixits', [])):
                out_lines.append(fix)
            out_lines.append('########')
            out_lines.append('')

        # Add continent-level FIX IT
        for fix in sorted(data.get('_fixits', [])):
            out_lines.append(fix)

    return '\n'.join(out_lines)


def main():
    if len(sys.argv) != 3:
        print("Usage: python sort_foreca_fixed.py input.txt output.txt")
        sys.exit(1)

    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        content = f.read()

    continents = parse_foreca_list(content)
    result = sort_and_output(continents)

    with open(sys.argv[2], 'w', encoding='utf-8') as f:
        f.write(result)

    print(f"Done. Output written to {sys.argv[2]}")


if __name__ == '__main__':
    main()
