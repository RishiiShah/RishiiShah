import unittest
from datetime import date
import json
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from generate_stats import Calendar, percentages, summarize, collect_metrics, overview, language_mix


class ProfileStatsTests(unittest.TestCase):
    def test_calendar_parses_zero_singular_and_plural_and_rejects_gaps(self):
        parser = Calendar()
        parser.feed('''
          <td id="a" data-date="2026-01-01"></td>
          <tool-tip for="a">No contributions on January 1st.</tool-tip>
          <td id="b" data-date="2026-01-02"></td>
          <tool-tip for="b">1 contribution on January 2nd.</tool-tip>
          <td id="c" data-date="2026-01-03"></td>
          <tool-tip for="c">1,234 contributions on January 3rd.</tool-tip>
        ''')
        result = parser.days(date(2026, 1, 1), date(2026, 1, 3))
        self.assertEqual(list(result.values()), [0, 1, 1234])
        with self.assertRaises(ValueError):
            parser.days(date(2026, 1, 1), date(2026, 1, 4))

    def test_all_charts_account_for_the_same_snapshot(self):
        snapshot = {
            'date': '2026-02-02',
            'contributions': {'2026-01-01': 3, '2026-02-02': 4},
            'repositories': [
                {'primary_language': 'Python', 'language_bytes': {'Python': 12, 'HTML': 3}},
                {'primary_language': None, 'language_bytes': {}},
                {'primary_language': 'Python', 'language_bytes': {'Python': 8}},
            ],
        }
        months, primary, languages = summarize(snapshot)
        self.assertEqual(sum(months.values()), 7)
        self.assertEqual(dict(primary), {'Python': 2, 'Unclassified': 1})
        self.assertEqual(dict(languages), {'Python': 20, 'HTML': 3})
        self.assertEqual(sum(primary.values()), len(snapshot['repositories']))

    def test_metrics_are_public_and_use_explicit_date_windows(self):
        payloads = [json.dumps({'total_count': n, 'incomplete_results': False}) for n in (12, 5, 3)]
        with patch('generate_stats.fetch', side_effect=payloads) as fetch:
            result = collect_metrics(date(2026, 1, 1), date(2026, 11, 7))
        self.assertEqual(result, {'commits': 12, 'prs': 5, 'merged_prs': 3})
        queries = [parse_qs(urlparse(call.args[0]).query)['q'][0] for call in fetch.call_args_list]
        self.assertTrue(all('is:public' in q for q in queries))
        self.assertIn('committer-date:2026-01-01..2026-11-07', queries[0])
        self.assertIn('created:2026-01-01..2026-11-07', queries[2])
        self.assertIn('is:merged', queries[2])

    def test_invalid_metrics_fail_instead_of_publishing_misleading_counts(self):
        for payload in ({'total_count': 10, 'incomplete_results': True},
                        {'total_count': -1, 'incomplete_results': False},
                        {'total_count': True, 'incomplete_results': False}, {}):
            with patch('generate_stats.fetch', return_value=json.dumps(payload)):
                with self.assertRaises(ValueError):
                    collect_metrics(date(2026, 1, 1), date(2026, 1, 2))
        payloads = [json.dumps({'total_count': n, 'incomplete_results': False}) for n in (12, 2, 3)]
        with patch('generate_stats.fetch', side_effect=payloads):
            with self.assertRaises(ValueError):
                collect_metrics(date(2026, 1, 1), date(2026, 1, 2))

    def test_cards_render_empty_data_long_labels_and_both_layouts(self):
        import xml.etree.ElementTree as ET
        snapshot = {'date': '2026-01-01', 'start': '2026-01-01',
                    'contributions': {'2026-01-01': 0}, 'repositories': [],
                    'metrics': {'commits': 0, 'prs': 0, 'merged_prs': 0}}
        for mode in ('dark', 'light'):
            for compact in (False, True):
                for counter in ({}, {'Jupyter Notebook': 20, 'C++': 8, 'A&B': 2}):
                    for image in (overview(snapshot, mode, compact),
                                  language_mix(snapshot, counter, mode, compact)):
                        ET.fromstring(image)
                        self.assertNotIn('nan', image)
                self.assertIn('No language data', language_mix(snapshot, {}, mode, compact))
        self.assertIn('1,234', overview({**snapshot, 'metrics': {**snapshot['metrics'], 'commits': 1234}}, 'dark'))

    def test_percentage_rounding_preserves_totals(self):
        self.assertEqual(sum(percentages([1, 1, 1])), 1000)
        self.assertEqual(percentages([0, 0]), [0, 0])


if __name__ == '__main__':
    unittest.main()
