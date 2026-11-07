import unittest
from datetime import date

from generate_stats import Calendar, percentages, summarize, top_rows


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

    def test_language_rollup_and_rounding_preserve_totals(self):
        languages = {str(i): i + 1 for i in range(12)}
        rows = top_rows(languages)
        self.assertEqual(len(rows), 8)
        self.assertEqual(sum(value for _, value in rows), sum(languages.values()))
        self.assertEqual(sum(percentages([1, 1, 1])), 1000)
        self.assertEqual(percentages([0, 0]), [0, 0])


if __name__ == '__main__':
    unittest.main()
